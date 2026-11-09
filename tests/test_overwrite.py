import os

import pytest

from nexplorer import overwrite
from nexplorer.protocol import Listener, RemoteError
from nexplorer.transfer import receive, send
from tests.fake_next import FakeNext

FS = {
    "c:/dest": None,
    "c:/dest/a.txt": b"old-a",
    "c:/dest/sub": None,
    "c:/dest/sub/x.txt": b"old-x",
    "c:/dest/sub/keep.txt": b"keep",
}


@pytest.fixture
def session():
    listener = Listener(host="127.0.0.1", port=0)
    listener.start()
    nxt = FakeNext(listener.port, fs=dict(FS), free_blocks={"C": 2048})
    nxt.connect()
    yield listener.wait_session(timeout=2), nxt
    nxt.drop()
    listener.stop()


def test_send_collisions_ignore_case_and_merge_folders(session, tmp_path):
    s, _ = session
    (tmp_path / "A.TXT").write_bytes(b"new")
    (tmp_path / "fresh.txt").write_bytes(b"f")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "x.txt").write_bytes(b"n")
    (tmp_path / "sub" / "other.txt").write_bytes(b"n")
    paths = [str(tmp_path / n) for n in ("A.TXT", "fresh.txt", "sub")]
    assert overwrite.send_collisions(s, paths, "c:/dest") == ["c:/dest/A.TXT", "c:/dest/sub/x.txt"]


def test_send_without_collision_finds_nothing(session, tmp_path):
    s, _ = session
    (tmp_path / "fresh.txt").write_bytes(b"f")
    assert overwrite.send_collisions(s, [str(tmp_path / "fresh.txt")], "c:/dest") == []


def test_a_destination_that_cannot_be_listed_raises(session, tmp_path):
    s, _ = session
    (tmp_path / "a.txt").write_bytes(b"f")
    with pytest.raises((RemoteError, OSError)):
        overwrite.send_collisions(s, [str(tmp_path / "a.txt")], "c:/nowhere")


def test_receive_collisions_merge_folders(session, tmp_path):
    s, _ = session
    (tmp_path / "a.txt").write_bytes(b"mine")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "x.txt").write_bytes(b"mine")
    found = overwrite.receive_collisions(s, "c:/dest", s.list_dir("c:/dest"), str(tmp_path))
    assert sorted(found) == [str(tmp_path / "a.txt"), str(tmp_path / "sub" / "x.txt")]


def test_send_skips_the_given_destination_paths(session, tmp_path):
    s, nxt = session
    (tmp_path / "a.txt").write_bytes(b"new")
    (tmp_path / "b.txt").write_bytes(b"new-b")
    result = send(s, [str(tmp_path / "a.txt"), str(tmp_path / "b.txt")], "c:/dest", skip=["c:/DEST/a.txt"])
    assert not result.failures
    assert nxt.fs["c:/dest/a.txt"] == b"old-a"
    assert nxt.fs["c:/dest/b.txt"] == b"new-b"


def test_receive_skips_the_given_local_paths(session, tmp_path):
    s, _ = session
    (tmp_path / "a.txt").write_bytes(b"mine")
    result = receive(s, "c:/dest", s.list_dir("c:/dest"), str(tmp_path), skip=[str(tmp_path / "a.txt")])
    assert not result.failures
    assert (tmp_path / "a.txt").read_bytes() == b"mine"
    assert (tmp_path / "sub" / "x.txt").read_bytes() == b"old-x"


def test_receive_collisions_use_the_spelling_the_transfer_writes_so_skip_agrees(session, tmp_path, monkeypatch):
    """On a case-insensitive Local file system the file on disk is `A.TXT`; the collision
    must name the path the transfer would write (`a.txt`) so that skipping it holds."""
    s, _ = session
    (tmp_path / "A.TXT").write_bytes(b"mine")
    real_lexists, real_isdir = os.path.lexists, os.path.isdir

    def fold(real):
        return lambda p: real(p) or (
            os.path.dirname(p) == str(tmp_path) and os.path.basename(p).lower() == "a.txt"
        )

    monkeypatch.setattr(os.path, "lexists", fold(real_lexists))
    monkeypatch.setattr(os.path, "isdir", lambda p: real_isdir(p))
    entries = [e for e in s.list_dir("c:/dest") if e.name == "a.txt"]
    found = overwrite.receive_collisions(s, "c:/dest", entries, str(tmp_path))
    assert found == [os.path.join(str(tmp_path), "a.txt")]
    result = receive(s, "c:/dest", entries, str(tmp_path), skip=found)
    assert not result.failures
    assert (tmp_path / "A.TXT").read_bytes() == b"mine"
    assert not (tmp_path / "a.txt").exists() or (tmp_path / "A.TXT").exists()

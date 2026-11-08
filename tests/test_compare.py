from nexplorer.compare import compare_level
from nexplorer.protocol import Entry


def row(rows, name):
    return next(r for r in rows if r.name == name)


def test_a_file_only_on_local_is_proposed_from_local_to_the_next_and_checked():
    rows = compare_level([Entry("a.tap", False, 10)], [])
    r = row(rows, "a.tap")
    assert (r.state, r.direction, r.checked) == ("only-local", "to-next", True)


def test_a_file_only_on_the_next_is_proposed_from_the_next_to_local_and_checked():
    rows = compare_level([], [Entry("b.tap", False, 10)])
    r = row(rows, "b.tap")
    assert (r.state, r.direction, r.checked) == ("only-next", "to-local", True)


def test_files_of_different_size_are_different_unchecked_and_without_direction():
    rows = compare_level([Entry("c.tap", False, 10)], [Entry("c.tap", False, 11)])
    r = row(rows, "c.tap")
    assert (r.state, r.direction, r.checked) == ("different", None, False)


def test_files_of_the_same_size_are_identical_and_have_nothing_to_transfer():
    rows = compare_level([Entry("d.tap", False, 10)], [Entry("d.tap", False, 10)])
    r = row(rows, "d.tap")
    assert (r.state, r.direction, r.checked) == ("identical", None, False)


def test_reversing_a_row_flips_its_direction_and_a_row_can_be_checked_or_unchecked():
    rows = compare_level([Entry("a.tap", False, 10)], [])
    r = row(rows, "a.tap")
    r.reverse()
    assert r.direction == "to-local"
    r.reverse()
    assert r.direction == "to-next"
    r.checked = False
    assert not r.checked


def test_a_different_row_gets_a_direction_when_the_user_first_reverses_it():
    r = row(compare_level([Entry("c.tap", False, 10)], [Entry("c.tap", False, 11)]), "c.tap")
    r.reverse()
    assert r.direction == "to-next"


import pytest

from nexplorer.compare import apply
from nexplorer.protocol import Listener
from tests.fake_next import FakeNext


@pytest.fixture
def listener():
    l = Listener(host="127.0.0.1", port=0)
    l.start()
    yield l
    l.stop()


def _session_with(listener, **fake_kwargs):
    nxt = FakeNext(listener.port, drives="CDM", **fake_kwargs)
    nxt.connect()
    return nxt, listener.wait_session(timeout=2)


def _rows(tmp_path, nxt_fs):
    local = [Entry(p.name, p.is_dir(), p.stat().st_size if p.is_file() else 0) for p in sorted(tmp_path.iterdir())]
    remote = [
        Entry(path.rsplit("/", 1)[1], data is None, len(data or b""))
        for path, data in nxt_fs.items()
        if path.startswith("d:/dest/") and path.count("/") == 2
    ]
    return compare_level(local, remote)


def test_apply_transfers_every_checked_row_in_its_direction_and_deletes_nothing(listener, tmp_path):
    (tmp_path / "up.tap").write_bytes(b"up")
    (tmp_path / "same.tap").write_bytes(b"ss")
    (tmp_path / "skipped.tap").write_bytes(b"skip")
    (tmp_path / "clash.tap").write_bytes(b"local-version")
    nxt, session = _session_with(
        listener,
        fs={
            "d:/dest": None,
            "d:/dest/down.tap": b"down",
            "d:/dest/same.tap": b"ss",
            "d:/dest/clash.tap": b"next",
        },
    )
    rows = _rows(tmp_path, nxt.fs)
    row(rows, "skipped.tap").checked = False
    row(rows, "clash.tap").reverse()  # to-next
    row(rows, "clash.tap").checked = True

    result = apply(session, str(tmp_path), "d:/dest", rows)

    assert result.failures == []
    assert nxt.fs["d:/dest/up.tap"] == b"up"
    assert nxt.fs["d:/dest/clash.tap"] == b"local-version"
    assert (tmp_path / "down.tap").read_bytes() == b"down"
    assert "d:/dest/skipped.tap" not in nxt.fs
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "clash.tap", "down.tap", "same.tap", "skipped.tap", "up.tap"
    ]
    assert set(nxt.fs) >= {"d:/dest/down.tap", "d:/dest/same.tap"}
    nxt.drop()


def test_a_reversed_one_sided_row_has_no_source_so_nothing_moves_and_nothing_is_deleted(listener, tmp_path):
    (tmp_path / "only.tap").write_bytes(b"only")
    nxt, session = _session_with(listener, fs={"d:/dest": None})
    rows = _rows(tmp_path, nxt.fs)
    row(rows, "only.tap").reverse()

    result = apply(session, str(tmp_path), "d:/dest", rows)

    assert result.failures == []
    assert (tmp_path / "only.tap").read_bytes() == b"only"
    assert set(nxt.fs) == {"d:/dest"}
    nxt.drop()


def test_a_folder_on_both_sides_is_not_scanned_and_has_nothing_to_transfer():
    r = row(compare_level([Entry("games", True, 0)], [Entry("games", True, 0)]), "games")
    assert (r.state, r.direction, r.checked, r.children) == ("not-scanned", None, False, None)

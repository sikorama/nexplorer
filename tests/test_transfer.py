import os

import pytest

from nexplorer.protocol import Entry, Listener
from nexplorer.transfer import receive, send
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


def test_send_puts_files_and_folders_recursively_on_the_next(listener, tmp_path):
    (tmp_path / "a.txt").write_bytes(b"alpha")
    tree = tmp_path / "games"
    (tree / "sub").mkdir(parents=True)
    (tree / "empty").mkdir()
    (tree / "one.tap").write_bytes(b"1" * 700)
    (tree / "sub" / "two.tap").write_bytes(b"2" * 30)
    nxt, session = _session_with(listener, fs={"d:/dest": None})

    result = send(session, [str(tmp_path / "a.txt"), str(tree)], "d:/dest")

    assert result.failures == []
    assert nxt.fs == {
        "d:/dest": None,
        "d:/dest/a.txt": b"alpha",
        "d:/dest/games": None,
        "d:/dest/games/empty": None,
        "d:/dest/games/sub": None,
        "d:/dest/games/one.tap": b"1" * 700,
        "d:/dest/games/sub/two.tap": b"2" * 30,
    }
    nxt.drop()


def test_send_reports_a_truncated_upload_found_by_the_size_check(listener, tmp_path):
    (tmp_path / "small.bin").write_bytes(b"s" * 50)
    (tmp_path / "big.bin").write_bytes(b"b" * 700)
    nxt, session = _session_with(
        listener,
        fs={"d:/dest": None},
        truncate_puts_to=100,
        truncated_put_reports_failure=False,  # the put looks fine: only the listing tells
    )

    result = send(session, [str(tmp_path / "small.bin"), str(tmp_path / "big.bin")], "d:/dest")

    assert [f.name for f in result.failures] == ["d:/dest/big.bin"]
    assert "100" in result.failures[0].reason and "700" in result.failures[0].reason
    nxt.drop()


def test_send_reports_a_failed_put_with_the_partial_file_and_goes_on(listener, tmp_path):
    (tmp_path / "big.bin").write_bytes(b"b" * 700)
    (tmp_path / "ok.bin").write_bytes(b"o" * 50)
    nxt, session = _session_with(listener, fs={"d:/dest": None}, truncate_puts_to=100)

    result = send(session, [str(tmp_path / "big.bin"), str(tmp_path / "ok.bin")], "d:/dest")

    assert [f.name for f in result.failures] == ["d:/dest/big.bin"]
    assert "100" in result.failures[0].reason  # the partial file's size, for the user to remove
    assert nxt.fs["d:/dest/ok.bin"] == b"o" * 50
    nxt.drop()


def test_receive_gets_files_and_folders_recursively_and_deletes_nothing_locally(listener, tmp_path):
    nxt, session = _session_with(
        listener,
        fs={
            "d:/games": None,
            "d:/games/empty": None,
            "d:/games/sub": None,
            "d:/games/one.tap": b"1" * 1500,
            "d:/games/sub/two.tap": b"2" * 30,
            "d:/a.txt": b"alpha",
        },
    )
    (tmp_path / "already.txt").write_bytes(b"mine")
    entries = session.list_dir("d:/", timeout=2)

    result = receive(session, "d:/", entries, str(tmp_path))

    assert result.failures == []
    assert (tmp_path / "a.txt").read_bytes() == b"alpha"
    assert (tmp_path / "games" / "one.tap").read_bytes() == b"1" * 1500
    assert (tmp_path / "games" / "sub" / "two.tap").read_bytes() == b"2" * 30
    assert (tmp_path / "games" / "empty").is_dir()
    assert (tmp_path / "already.txt").read_bytes() == b"mine"
    nxt.drop()


def test_send_reports_progress_with_the_current_file_up_to_100_percent(listener, tmp_path):
    (tmp_path / "a.bin").write_bytes(b"a" * 1200)
    (tmp_path / "b.bin").write_bytes(b"b" * 400)
    nxt, session = _session_with(listener, fs={"d:/dest": None})
    seen = []

    send(
        session,
        [str(tmp_path / "a.bin"), str(tmp_path / "b.bin")],
        "d:/dest",
        progress=lambda name, percent: seen.append((name, percent)),
    )

    percents = [p for _, p in seen]
    assert percents == sorted(percents) and percents[-1] == 100
    assert {n for n, _ in seen} == {"a.bin", "b.bin"}
    assert any(0 < p < 100 for n, p in seen if n == "a.bin")  # moves within a file
    nxt.drop()


def test_cancel_stops_the_send_before_the_remaining_files(listener, tmp_path):
    for name in ("a.bin", "b.bin", "c.bin"):
        (tmp_path / name).write_bytes(b"x" * 100)
    nxt, session = _session_with(listener, fs={"d:/dest": None})
    started = []

    result = send(
        session,
        [str(tmp_path / n) for n in ("a.bin", "b.bin", "c.bin")],
        "d:/dest",
        progress=lambda name, percent: started.append(name),
        cancel=lambda: "a.bin" in started and len(set(started)) > 1,
    )

    assert result.cancelled
    assert "d:/dest/a.bin" in nxt.fs and "d:/dest/c.bin" not in nxt.fs
    nxt.drop()


def test_cancel_during_a_file_reports_the_partial_file_left_on_the_next(listener, tmp_path):
    (tmp_path / "big.bin").write_bytes(b"x" * 5000)
    nxt, session = _session_with(listener, fs={"d:/dest": None})
    chunks = []

    result = send(
        session,
        [str(tmp_path / "big.bin")],
        "d:/dest",
        progress=lambda name, percent: chunks.append(percent),
        cancel=lambda: len(chunks) >= 2,
    )

    assert result.cancelled
    assert [f.name for f in result.failures] == ["d:/dest/big.bin"]
    assert 0 < len(nxt.fs["d:/dest/big.bin"]) < 5000  # nothing is deleted on the Next
    assert session.dot_version(timeout=2) == "5.9.14"  # the Session stays in step
    nxt.drop()


@pytest.mark.parametrize("bad", ["..", ".", "sub/x.txt", "sub\\x.txt", "/etc/x.txt", "c:x.txt", ""])
def test_receive_refuses_an_entry_name_that_would_leave_the_local_folder(listener, tmp_path, bad):
    out = tmp_path / "out"
    out.mkdir()
    (tmp_path / "x.txt").write_bytes(b"precious")
    nxt, session = _session_with(
        listener, fs={"d:/src": None, "d:/src/ok.txt": b"fine", "d:/x.txt": b"evil"}
    )
    entries = [Entry(bad, False, 4), Entry("ok.txt", False, 4)]

    result = receive(session, "d:/src", entries, str(out))

    assert [f.name for f in result.failures] == [f"d:/src/{bad}"]
    assert "unsafe" in result.failures[0].reason
    assert (out / "ok.txt").read_bytes() == b"fine"  # the other entries go on
    assert sorted(p.name for p in out.iterdir()) == ["ok.txt"]
    assert (tmp_path / "x.txt").read_bytes() == b"precious"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out", "x.txt"]
    nxt.drop()


def test_send_reports_the_files_when_the_session_dies_instead_of_raising(listener, tmp_path):
    (tmp_path / "a.txt").write_bytes(b"alpha")
    (tmp_path / "b.txt").write_bytes(b"beta")
    nxt, session = _session_with(listener, fs={"d:/dest": None})

    def drop_before_b(name, percent):
        if name == "b.txt":
            nxt.drop()
            session.wait_closed(timeout=2)

    result = send(
        session, [str(tmp_path / "a.txt"), str(tmp_path / "b.txt")], "d:/dest", progress=drop_before_b
    )

    assert sorted(f.name for f in result.failures) == ["d:/dest/a.txt", "d:/dest/b.txt"]
    assert "not checked" in next(f for f in result.failures if f.name.endswith("a.txt")).reason


def test_a_cancelled_send_stays_cancelled_when_the_size_check_cannot_run(listener, tmp_path):
    (tmp_path / "a.txt").write_bytes(b"alpha")
    (tmp_path / "b.txt").write_bytes(b"beta")
    (tmp_path / "c.txt").write_bytes(b"gamma")
    nxt, session = _session_with(listener, fs={"d:/dest": None})
    cancelled = []

    def cancel():
        if cancelled:
            return True
        return False

    def drop_then_cancel(name, percent):
        if name == "b.txt":
            nxt.drop()
            session.wait_closed(timeout=2)
            cancelled.append(True)

    result = send(
        session, [str(tmp_path / n) for n in ("a.txt", "b.txt", "c.txt")], "d:/dest",
        progress=drop_then_cancel, cancel=cancel,
    )

    assert result.cancelled


def test_send_reports_a_folder_that_cannot_be_created_once_instead_of_every_file(listener, tmp_path):
    tree = tmp_path / "games"
    (tree / "sub").mkdir(parents=True)
    (tree / "one.tap").write_bytes(b"1")
    (tree / "sub" / "two.tap").write_bytes(b"2")
    nxt, session = _session_with(listener, fs={"d:/dest": None})

    result = send(session, [str(tree)], "d:/missing/parent")  # make_dir fails: no such parent

    assert [f.name for f in result.failures] == ["d:/missing/parent/games"]
    assert b"P" not in nxt.commands
    nxt.drop()


def test_send_goes_on_into_a_folder_that_already_exists(listener, tmp_path):
    tree = tmp_path / "games"
    tree.mkdir()
    (tree / "one.tap").write_bytes(b"1")
    nxt, session = _session_with(listener, fs={"d:/dest": None, "d:/dest/games": None})

    result = send(session, [str(tree)], "d:/dest")

    assert result.failures == []
    assert nxt.fs["d:/dest/games/one.tap"] == b"1"
    nxt.drop()


def test_send_survives_a_symlink_loop_and_a_broken_symlink(listener, tmp_path):
    tree = tmp_path / "games"
    tree.mkdir()
    (tree / "one.tap").write_bytes(b"1")
    (tree / "loop").symlink_to(tree)
    (tree / "dangling").symlink_to(tmp_path / "nowhere")
    nxt, session = _session_with(listener, fs={"d:/dest": None})

    result = send(session, [str(tree)], "d:/dest")

    assert nxt.fs["d:/dest/games/one.tap"] == b"1"
    assert sorted(f.name for f in result.failures) == ["d:/dest/games/dangling", "d:/dest/games/loop"]
    assert not any(k.startswith("d:/dest/games/loop/") for k in nxt.fs)
    nxt.drop()


def test_send_reports_two_local_names_that_differ_only_by_case(listener, tmp_path):
    (tmp_path / "Game.tap").write_bytes(b"upper")
    (tmp_path / "game.tap").write_bytes(b"lower")
    nxt, session = _session_with(listener, fs={"d:/dest": None})

    result = send(session, [str(tmp_path / "Game.tap"), str(tmp_path / "game.tap")], "d:/dest")

    assert len(result.failures) == 1
    assert "same name" in result.failures[0].reason
    assert len([k for k in nxt.fs if k.endswith("game.tap")]) == 1  # only one was put
    assert nxt.commands.count(b"P") == 1
    nxt.drop()


def test_send_reports_a_folder_when_the_session_dies_before_it_is_created(listener, tmp_path):
    tree = tmp_path / "games"
    tree.mkdir()
    (tree / "one.tap").write_bytes(b"1")
    nxt, session = _session_with(listener, fs={"d:/dest": None})
    nxt.drop()
    session.wait_closed(timeout=2)

    result = send(session, [str(tree)], "d:/dest")

    assert [f.name for f in result.failures] == ["d:/dest/games"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any folder")
def test_send_reports_an_unreadable_local_folder_and_sends_the_rest(listener, tmp_path):
    tree = tmp_path / "games"
    locked = tree / "locked"
    locked.mkdir(parents=True)
    (tree / "one.tap").write_bytes(b"1")
    locked.chmod(0)
    nxt, session = _session_with(listener, fs={"d:/dest": None})
    try:
        result = send(session, [str(tree)], "d:/dest")
    finally:
        locked.chmod(0o700)

    assert nxt.fs["d:/dest/games/one.tap"] == b"1"
    assert [f.name for f in result.failures] == ["d:/dest/games/locked"]
    nxt.drop()


def test_send_progress_counts_the_contents_of_symlinked_folders(listener, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "big.tap").write_bytes(b"b" * 900)
    tree = tmp_path / "games"
    tree.mkdir()
    (tree / "real.tap").write_bytes(b"r" * 100)
    (tree / "linked").symlink_to(outside)
    nxt, session = _session_with(listener, fs={"d:/dest": None})
    seen = []

    result = send(session, [str(tree)], "d:/dest", progress=lambda n, p: seen.append((n, p)))

    assert result.failures == []
    assert max(p for n, p in seen if n == "real.tap") == 10  # 100 of 1000 bytes
    assert seen[-1][1] == 100
    nxt.drop()


def test_send_reports_a_folder_and_a_file_that_differ_only_by_case(listener, tmp_path):
    (tmp_path / "Data").write_bytes(b"file")
    folder = tmp_path / "data"
    folder.mkdir()
    (folder / "x.bin").write_bytes(b"x")
    nxt, session = _session_with(listener, fs={"d:/dest": None})

    result = send(session, [str(tmp_path / "Data"), str(folder)], "d:/dest")

    assert nxt.fs["d:/dest/data"] == b"file"
    assert [f.name for f in result.failures] == ["d:/dest/data"]
    assert "same name" in result.failures[0].reason
    assert "d:/dest/data/x.bin" not in nxt.fs
    nxt.drop()


def test_receive_reports_progress_inside_a_single_file(listener, tmp_path):
    content = b"r" * 5000  # five D blocks
    nxt, session = _session_with(listener, fs={"d:/src": None, "d:/src/big.bin": content})
    seen = []

    result = receive(
        session, "d:/src", [Entry("big.bin", False, 5000)], str(tmp_path),
        progress=lambda name, percent: seen.append((name, percent)),
    )

    assert result.failures == []
    percents = [p for _, p in seen]
    assert percents == sorted(percents) and percents[-1] == 100
    assert any(0 < p < 100 for p in percents)  # the bar moves while the file comes in
    assert {n for n, _ in seen} == {"big.bin"}
    nxt.drop()


def test_receive_of_a_folder_skips_dot_entries_and_reports_progress_over_its_whole_content(listener, tmp_path):
    fs = {
        "d:/src": None,
        "d:/src/tree": None,
        "d:/src/tree/.": None,
        "d:/src/tree/..": None,
        "d:/src/tree/a.bin": b"a" * 3000,
        "d:/src/tree/sub": None,
        "d:/src/tree/sub/.": None,
        "d:/src/tree/sub/..": None,
        "d:/src/tree/sub/b.bin": b"b" * 1000,
    }
    nxt, session = _session_with(listener, fs=fs)
    seen = []

    result = receive(
        session, "d:/src", [Entry("tree", True, 0)], str(tmp_path),
        progress=lambda name, percent: seen.append((name, percent)),
    )

    assert result.failures == []
    assert (tmp_path / "tree" / "a.bin").read_bytes() == b"a" * 3000
    assert (tmp_path / "tree" / "sub" / "b.bin").read_bytes() == b"b" * 1000
    percents = [p for _, p in seen]
    assert percents == sorted(percents) and percents[-1] == 100
    assert percents[0] < 100 and any(0 < p < 100 for p in percents)  # the bar is not at 100 from the start
    nxt.drop()


def test_cancel_during_the_scan_of_a_receive_stops_it(listener, tmp_path):
    fs = {"d:/src": None, "d:/src/t": None, "d:/src/t/a.bin": b"a"}
    nxt, session = _session_with(listener, fs=fs)

    result = receive(session, "d:/src", [Entry("t", True, 0)], str(tmp_path), cancel=lambda: True)

    assert result.cancelled
    assert list(tmp_path.iterdir()) == []
    nxt.drop()


REMOVE_FS = {
    "d:/dest": None,
    "d:/dest/games": None,
    "d:/dest/games/one.tap": b"1",
    "d:/dest/games/sub": None,
    "d:/dest/games/sub/two.tap": b"2",
    "d:/dest/games/empty": None,
    "d:/dest/keep.txt": b"k",
    "d:/dest/note.txt": b"n",
}


def test_remove_deletes_files_and_non_empty_folders_leaving_the_rest(listener):
    from nexplorer.transfer import remove

    nxt, session = _session_with(listener, fs=REMOVE_FS)
    entries = [Entry("games", True, 0), Entry("note.txt", False, 1)]
    seen = []
    result = remove(session, "d:/dest", entries, progress=lambda n, p: seen.append(p))
    assert result.failures == [] and not result.cancelled
    assert nxt.fs == {"d:/dest": None, "d:/dest/keep.txt": b"k"}
    assert seen and seen[-1] == 100
    nxt.drop()


def test_remove_reports_a_failing_item_and_carries_on(listener):
    from nexplorer.transfer import remove

    nxt, session = _session_with(listener, fs=REMOVE_FS)
    result = remove(session, "d:/dest", [Entry("ghost.txt", False, 1), Entry("note.txt", False, 1)])
    assert [f.name for f in result.failures] == ["d:/dest/ghost.txt"]
    assert "d:/dest/note.txt" not in nxt.fs
    nxt.drop()


def test_remove_stops_when_cancelled_and_deletes_nothing_more(listener):
    from nexplorer.transfer import remove

    nxt, session = _session_with(listener, fs=REMOVE_FS)
    calls = []

    def cancel():
        calls.append(1)
        return len(calls) > 3  # scanning one folder level costs checks; stop during the deletes

    result = remove(session, "d:/dest", [Entry("note.txt", False, 1), Entry("keep.txt", False, 1)], cancel=cancel)
    assert result.cancelled
    assert "d:/dest/keep.txt" in nxt.fs
    nxt.drop()


def test_remove_refuses_unsafe_names_without_sending_anything(listener):
    from nexplorer.transfer import remove

    nxt, session = _session_with(listener, fs=REMOVE_FS)
    result = remove(session, "d:/dest", [Entry("..", True, 0), Entry("a/b", False, 1)])
    assert len(result.failures) == 2
    assert b"X" not in nxt.commands and b"R" not in nxt.commands
    nxt.drop()


MOVE_FS = {
    "c:/src": None,
    "c:/src/game": None,
    "c:/src/game/one.tap": b"1" * 50,
    "c:/src/game/sub": None,
    "c:/src/game/sub/two.tap": b"2" * 20,
    "c:/src/note.txt": b"note",
    "c:/dst": None,
    "m:/dst": None,
}


def _entries(*items):
    return [Entry(n, d, s) for n, d, s in items]


def test_copy_duplicates_entries_into_another_folder_and_keeps_the_sources(listener):
    from nexplorer.transfer import copy

    nxt, session = _session_with(listener, fs=MOVE_FS)
    result = copy(session, "c:/src", _entries(("game", True, 0), ("note.txt", False, 4)), "c:/dst")
    assert result.failures == []
    assert nxt.fs["c:/dst/game/sub/two.tap"] == b"2" * 20 and nxt.fs["c:/dst/note.txt"] == b"note"
    assert "c:/src/game/one.tap" in nxt.fs and "c:/src/note.txt" in nxt.fs
    nxt.drop()


def test_copy_refuses_an_existing_name_and_a_folder_into_itself(listener):
    from nexplorer.transfer import copy

    fs = dict(MOVE_FS, **{"c:/dst/note.txt": b"keep me"})
    nxt, session = _session_with(listener, fs=fs)
    result = copy(session, "c:/src", _entries(("note.txt", False, 4)), "c:/dst")
    assert [f.name for f in result.failures] == ["c:/src/note.txt"]
    assert nxt.fs["c:/dst/note.txt"] == b"keep me"
    result = copy(session, "c:/src", _entries(("game", True, 0)), "c:/src/game/sub")
    assert len(result.failures) == 1
    assert b"C" not in nxt.commands
    nxt.drop()


def test_move_on_the_same_drive_is_a_rename_with_no_copy(listener):
    from nexplorer.transfer import move

    nxt, session = _session_with(listener, fs=MOVE_FS)
    result = move(session, "c:/src", _entries(("game", True, 0), ("note.txt", False, 4)), "c:/dst")
    assert result.failures == []
    assert "c:/dst/game/sub/two.tap" in nxt.fs and "c:/dst/note.txt" in nxt.fs
    assert not any(k.startswith("c:/src/game") for k in nxt.fs) and "c:/src/note.txt" not in nxt.fs
    assert b"C" not in nxt.commands
    nxt.drop()


def test_move_across_drives_copies_checks_the_size_then_deletes_the_source(listener):
    from nexplorer.transfer import move

    nxt, session = _session_with(listener, fs=MOVE_FS)
    result = move(session, "c:/src", _entries(("game", True, 0), ("note.txt", False, 4)), "m:/dst")
    assert result.failures == [] and not result.cancelled
    assert nxt.fs["m:/dst/game/one.tap"] == b"1" * 50 and nxt.fs["m:/dst/game/sub/two.tap"] == b"2" * 20
    assert nxt.fs["m:/dst/note.txt"] == b"note"
    assert not any(k.startswith("c:/src/") for k in nxt.fs)
    assert nxt.commands.index(b"C") < nxt.commands.index(b"X")  # copied before anything is deleted
    nxt.drop()


def test_cross_drive_move_progress_counts_one_step_per_entry(listener):
    from nexplorer.transfer import move

    nxt, session = _session_with(listener, fs=MOVE_FS)
    seen = []
    move(session, "c:/src", _entries(("game", True, 0), ("note.txt", False, 4)), "m:/dst",
         progress=lambda name, percent: seen.append((name, percent)))
    assert seen == [("game", 50), ("note.txt", 100)]
    nxt.drop()


def test_a_failing_cross_drive_move_keeps_the_source_and_says_so(listener):
    from nexplorer.transfer import move

    nxt, session = _session_with(listener, fs=MOVE_FS, copy_fails_after=1)
    result = move(session, "c:/src", _entries(("game", True, 0)), "m:/dst")
    assert len(result.failures) == 1 and "kept" in result.failures[0].reason
    assert "c:/src/game/one.tap" in nxt.fs and "c:/src/game/sub/two.tap" in nxt.fs
    assert b"X" not in nxt.commands and b"R" not in nxt.commands
    nxt.drop()


def test_a_cross_drive_move_whose_copy_came_out_short_keeps_the_source(listener):
    from nexplorer.transfer import move

    nxt, session = _session_with(listener, fs=MOVE_FS, copy_silently_truncates=True)
    result = move(session, "c:/src", _entries(("note.txt", False, 4)), "m:/dst")
    assert len(result.failures) == 1 and "kept" in result.failures[0].reason
    assert nxt.fs["c:/src/note.txt"] == b"note"
    nxt.drop()


def test_move_refuses_an_existing_name_a_folder_into_itself_and_the_same_folder(listener):
    from nexplorer.transfer import move

    fs = dict(MOVE_FS, **{"c:/dst/note.txt": b"keep me"})
    nxt, session = _session_with(listener, fs=fs)
    result = move(
        session, "c:/src",
        _entries(("note.txt", False, 4), ("game", True, 0)),
        "c:/dst",
    )
    assert [f.name for f in result.failures] == ["c:/src/note.txt"]
    assert nxt.fs["c:/src/note.txt"] == b"note" and nxt.fs["c:/dst/note.txt"] == b"keep me"
    assert "c:/dst/game/one.tap" in nxt.fs  # the other entry still moved
    assert len(move(session, "c:/src", _entries(("note.txt", False, 4)), "c:/src").failures) == 1
    assert len(move(session, "c:/dst", _entries(("game", True, 0)), "c:/dst/game/sub").failures) == 1
    nxt.drop()


def test_send_with_crc_check_reports_a_same_size_corruption_the_size_check_cannot_see(listener, tmp_path):
    (tmp_path / "ok.bin").write_bytes(b"o" * 50)
    (tmp_path / "bad.bin").write_bytes(b"b" * 50)
    nxt, session = _session_with(listener, fs={"d:/dest": None}, corrupt_puts_of=("bad.bin",))

    result = send(session, [str(tmp_path / "ok.bin"), str(tmp_path / "bad.bin")], "d:/dest", verify_crc=True)

    assert [f.name for f in result.failures] == ["d:/dest/bad.bin"]
    assert "CRC" in result.failures[0].reason
    assert nxt.commands.count(b"K") == 2
    nxt.drop()


def test_send_does_not_ask_for_a_crc_by_default(listener, tmp_path):
    (tmp_path / "bad.bin").write_bytes(b"b" * 50)
    nxt, session = _session_with(listener, fs={"d:/dest": None}, corrupt_puts_of=("bad.bin",))

    result = send(session, [str(tmp_path / "bad.bin")], "d:/dest")

    assert result.failures == []  # same size: only the CRC could tell
    assert b"K" not in nxt.commands
    nxt.drop()


def test_crc_check_that_cannot_run_is_reported_not_raised(listener, tmp_path):
    (tmp_path / "a.bin").write_bytes(b"a" * 20)
    nxt, session = _session_with(listener, fs={"d:/dest": None}, ignores=frozenset({b"K"}))

    result = send(session, [str(tmp_path / "a.bin")], "d:/dest", verify_crc=True, timeout=0.3)

    assert [f.name for f in result.failures] == ["d:/dest/a.bin"]
    assert "CRC not checked" in result.failures[0].reason
    nxt.drop()


def test_a_session_lost_during_a_put_stops_the_batch_and_names_the_partial_file(listener, tmp_path):
    for name, size in (("a.bin", 100), ("b.bin", 2000), ("c.bin", 100)):
        (tmp_path / name).write_bytes(b"x" * size)
    nxt, session = _session_with(listener, fs={"d:/dest": None}, put_drops_at_chunk=("b.bin", 2))

    result = send(session, [str(tmp_path / n) for n in ("a.bin", "b.bin", "c.bin")], "d:/dest")

    assert result.dropped
    names = [f.name for f in result.failures]
    assert "d:/dest/c.bin" not in names  # never started: left as it was
    assert "d:/dest/c.bin" not in nxt.fs
    partial = next(f for f in result.failures if f.name == "d:/dest/b.bin")
    assert "1024 bytes" in partial.reason  # what had been sent when the link died
    assert nxt.fs["d:/dest/b.bin"] == b"x" * 1024  # and nothing was deleted


def test_a_session_lost_before_a_file_stops_the_batch_without_failing_the_untouched_files(listener, tmp_path):
    for name in ("a.txt", "b.txt", "c.txt"):
        (tmp_path / name).write_bytes(b"data")
    nxt, session = _session_with(listener, fs={"d:/dest": None})

    def drop_before_b(name, percent):
        if name == "b.txt":
            nxt.drop()
            session.wait_closed(timeout=2)

    result = send(session, [str(tmp_path / n) for n in ("a.txt", "b.txt", "c.txt")], "d:/dest",
                  progress=drop_before_b)

    assert result.dropped
    assert "d:/dest/c.txt" not in [f.name for f in result.failures]


def test_a_session_lost_during_a_receive_stops_it_and_keeps_what_came(listener, tmp_path):
    fs = {"d:/src": None, "d:/src/a.bin": b"a" * 50, "d:/src/b.bin": b"b" * 3000, "d:/src/c.bin": b"c" * 50}
    nxt, session = _session_with(listener, fs=fs, get_drops_after_blocks=2)
    entries = [Entry("a.bin", False, 50), Entry("b.bin", False, 3000), Entry("c.bin", False, 50)]

    result = receive(session, "d:/src", entries, str(tmp_path))

    assert result.dropped
    assert "d:/src/b.bin" in [f.name for f in result.failures]
    assert "d:/src/c.bin" not in [f.name for f in result.failures]
    assert (tmp_path / "a.bin").read_bytes() == b"a" * 50
    assert not (tmp_path / "c.bin").exists()


def test_cancel_stops_the_crc_checks_between_files(listener, tmp_path):
    for n in ("a.bin", "b.bin", "c.bin"):
        (tmp_path / n).write_bytes(b"x" * 20)
    nxt, session = _session_with(listener, fs={"d:/dest": None})

    result = send(session, [str(tmp_path / n) for n in ("a.bin", "b.bin", "c.bin")], "d:/dest",
                  verify_crc=True, cancel=lambda: nxt.commands.count(b"K") >= 1)

    assert result.cancelled
    assert nxt.commands.count(b"K") == 1
    nxt.drop()


def test_a_crc_check_that_times_out_is_not_repeated_for_the_other_files(listener, tmp_path):
    for n in ("a.bin", "b.bin"):
        (tmp_path / n).write_bytes(b"x" * 20)
    nxt, session = _session_with(listener, fs={"d:/dest": None}, ignores=frozenset({b"K"}))

    result = send(session, [str(tmp_path / n) for n in ("a.bin", "b.bin")], "d:/dest",
                  verify_crc=True, timeout=0.3)

    assert sorted(f.name for f in result.failures) == ["d:/dest/a.bin", "d:/dest/b.bin"]
    assert all("CRC not checked" in f.reason for f in result.failures)
    assert nxt.commands.count(b"K") == 1  # the dot is not answering: no point asking again
    nxt.drop()

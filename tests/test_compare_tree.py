"""Compare below one level: not scanned folders, expansion on demand, Scan all."""
import pytest

from nexplorer.compare import apply, compare_level, expand, scan_all
from nexplorer.protocol import Entry, Listener
from tests.fake_next import FakeNext


@pytest.fixture
def listener():
    l = Listener(host="127.0.0.1", port=0)
    l.start()
    yield l
    l.stop()


def row(rows, name):
    return next(r for r in rows if r.name == name)


def _session_with(listener, fs):
    nxt = FakeNext(listener.port, drives="CDM", fs=fs)
    nxt.connect()
    return nxt, listener.wait_session(timeout=2)


def _tree(tmp_path):
    (tmp_path / "games").mkdir()
    (tmp_path / "games" / "up.tap").write_bytes(b"up")
    (tmp_path / "games" / "same.tap").write_bytes(b"ss")
    (tmp_path / "games" / "deep").mkdir()
    (tmp_path / "games" / "deep" / "x.tap").write_bytes(b"x")
    (tmp_path / "top.tap").write_bytes(b"top")
    return {
        "d:/dest": None,
        "d:/dest/games": None,
        "d:/dest/games/same.tap": b"ss",
        "d:/dest/games/down.tap": b"down",
        "d:/dest/games/deep": None,
        "d:/dest/games/deep/x.tap": b"xy",
    }


def _top(tmp_path):
    local = [Entry(p.name, p.is_dir(), 0 if p.is_dir() else p.stat().st_size) for p in sorted(tmp_path.iterdir())]
    return compare_level(local, [Entry("games", True, 0)])


def test_expanding_a_folder_lists_its_next_level_with_the_same_states_and_proposals(listener, tmp_path):
    nxt, session = _session_with(listener, _tree(tmp_path))
    games = row(_top(tmp_path), "games")

    expand(session, games, str(tmp_path), "d:/dest")

    assert [(r.name, r.state, r.direction, r.checked) for r in sorted(games.children, key=lambda r: r.name)] == [
        ("deep", "not-scanned", None, False),
        ("down.tap", "only-next", "to-local", True),
        ("same.tap", "unverified", None, False),
        ("up.tap", "only-local", "to-next", True),
    ]
    assert games.state == "not-scanned"  # deep is still unknown
    nxt.drop()


def test_scan_all_expands_the_whole_tree_and_a_folder_is_identical_only_when_all_below_is(listener, tmp_path):
    nxt, session = _session_with(listener, _tree(tmp_path))
    rows = _top(tmp_path)

    result = scan_all(session, rows, str(tmp_path), "d:/dest")

    assert not result.cancelled and result.failures == []
    games = row(rows, "games")
    deep = row(games.children, "deep")
    assert [(r.name, r.state) for r in deep.children] == [("x.tap", "different")]
    assert (deep.state, games.state) == ("different", "different")
    nxt.drop()


def test_a_scanned_folder_of_same_size_files_is_unverified_not_identical(listener, tmp_path):
    (tmp_path / "games").mkdir()
    (tmp_path / "games" / "a.tap").write_bytes(b"aa")
    nxt, session = _session_with(listener, {"d:/dest": None, "d:/dest/games": None, "d:/dest/games/a.tap": b"aa"})
    rows = _top(tmp_path)

    scan_all(session, rows, str(tmp_path), "d:/dest")

    assert row(rows, "games").state == "unverified"
    nxt.drop()


def test_scan_all_reports_progress_and_cancel_leaves_unreached_folders_not_scanned(listener, tmp_path):
    nxt, session = _session_with(listener, _tree(tmp_path))
    rows = _top(tmp_path)
    seen = []

    result = scan_all(
        session, rows, str(tmp_path), "d:/dest",
        progress=lambda name, pct: seen.append(name), cancel=lambda: bool(seen),
    )

    assert result.cancelled
    games = row(rows, "games")
    assert seen == ["games"]
    assert games.state == "not-scanned"
    assert row(games.children, "deep").state == "not-scanned" and row(games.children, "deep").children is None
    nxt.drop()


def test_apply_transfers_checked_rows_found_inside_an_expanded_folder(listener, tmp_path):
    fs = _tree(tmp_path)
    nxt, session = _session_with(listener, fs)
    rows = _top(tmp_path)
    expand(session, row(rows, "games"), str(tmp_path), "d:/dest")
    row(rows, "top.tap").checked = False

    result = apply(session, str(tmp_path), "d:/dest", rows)

    assert result.failures == []
    assert nxt.fs["d:/dest/games/up.tap"] == b"up"
    assert (tmp_path / "games" / "down.tap").read_bytes() == b"down"
    assert "d:/dest/top.tap" not in nxt.fs
    nxt.drop()


def test_an_expanded_level_applies_the_naming_rules_and_is_never_transferred_when_blocked(listener, tmp_path):
    fs = _tree(tmp_path)
    for name in ("bad?.tap", "junk.bak", ".hid"):
        (tmp_path / "games" / name).write_bytes(b"x")
    nxt, session = _session_with(listener, fs)
    rows = _top(tmp_path)

    expand(session, row(rows, "games"), str(tmp_path), "d:/dest", show_hidden=False, ignore=["*.bak"])

    kids = row(rows, "games").children
    assert (row(kids, "bad?.tap").state, row(kids, "junk.bak").state, row(kids, ".hid").state) == (
        "invalid", "ignored", "hidden",
    )
    apply(session, str(tmp_path), "d:/dest", rows)
    assert set(nxt.fs) & {"d:/dest/games/bad?.tap", "d:/dest/games/junk.bak", "d:/dest/games/.hid"} == set()
    assert nxt.fs["d:/dest/games/up.tap"] == b"up"
    nxt.drop()

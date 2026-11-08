import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nexplorer.settings import Settings, save
from tests.conftest import pump
from tests.fake_next import FakeNext
from tests.test_window_settings import opened


def prepare(app, w, listener, tmp_path, nxt_fs):
    nxt = FakeNext(listener.port, fs={"c:/dest": None, **nxt_fs}, free_blocks={"C": 2048})
    nxt.connect()
    assert pump(app, lambda: w.next_pane_state() == "connected")
    assert pump(app, lambda: w.next_pane().path() == "c:/" and w.next_pane().names() == ["dest"])
    w.next_pane().enter("dest")
    assert pump(app, lambda: w.next_pane().path() == "c:/dest" and not w.next_pane().is_loading())
    assert pump(app, lambda: not w.local_pane().is_loading() and w.local_pane().path() == str(tmp_path / "local"))
    return nxt


def local_folder(tmp_path):
    folder = tmp_path / "local"
    folder.mkdir()
    (folder / "up.tap").write_bytes(b"up")
    (folder / "same.tap").write_bytes(b"ss")
    (folder / "clash.tap").write_bytes(b"local-version")
    path = tmp_path / "settings.json"
    save(Settings(local_folder=str(folder)), path)
    return path


NEXT_FS = {"c:/dest/down.tap": b"down", "c:/dest/same.tap": b"ss", "c:/dest/clash.tap": b"next"}


def test_compare_lists_the_differences_of_the_folders_shown_and_back_restores_the_panes(app, tmp_path):
    path = local_folder(tmp_path)
    with opened(app, path) as (w, listener):
        nxt = prepare(app, w, listener, tmp_path, NEXT_FS)
        w.compare()
        assert w.compare_active()
        assert sorted(w.compare_rows()) == [
            ("clash.tap", "different", "", False),
            ("down.tap", "only-next", "to-local", True),
            ("same.tap", "unverified", "", False),
            ("up.tap", "only-local", "to-next", True),
        ]
        w.compare_back()
        assert not w.compare_active()
        assert w.local_pane().path() == str(tmp_path / "local") and w.next_pane().path() == "c:/dest"
        nxt.drop()


def test_apply_transfers_the_checked_rows_and_a_single_row_can_go_alone(app, tmp_path):
    path = local_folder(tmp_path)
    with opened(app, path) as (w, listener):
        nxt = prepare(app, w, listener, tmp_path, NEXT_FS)
        w.compare()
        w.compare_transfer("up.tap")
        assert pump(app, lambda: w.operation_running())
        assert pump(app, lambda: not w.operation_running(), timeout=10)
        assert nxt.fs["c:/dest/up.tap"] == b"up"
        assert not (tmp_path / "local" / "down.tap").exists()

        w.compare_reverse("clash.tap")
        w.compare_set_checked("clash.tap", True)
        w.compare_set_checked("down.tap", True)
        w.compare_apply()
        assert pump(app, lambda: w.operation_running())
        assert pump(app, lambda: not w.operation_running(), timeout=10)
        assert (tmp_path / "local" / "down.tap").read_bytes() == b"down"
        assert nxt.fs["c:/dest/clash.tap"] == b"local-version"
        assert nxt.fs["c:/dest/same.tap"] == b"ss" and (tmp_path / "local" / "same.tap").exists()
        nxt.drop()


def nested_local(tmp_path):
    path = local_folder(tmp_path)
    games = tmp_path / "local" / "games"
    games.mkdir()
    (games / "a.tap").write_bytes(b"aa")
    (games / "deep").mkdir()
    (games / "deep" / "z.tap").write_bytes(b"z")
    return path


TREE_FS = {
    **NEXT_FS,
    "c:/dest/games": None,
    "c:/dest/games/a.tap": b"aa",
    "c:/dest/games/deep": None,
    "c:/dest/games/deep/z.tap": b"zz",
}


def test_a_folder_on_both_sides_is_not_scanned_until_expanded(app, tmp_path):
    path = nested_local(tmp_path)
    with opened(app, path) as (w, listener):
        nxt = prepare(app, w, listener, tmp_path, TREE_FS)
        w.compare()
        assert ("games", "not-scanned", "", False) in w.compare_rows()
        w.compare_expand("games")
        assert pump(app, lambda: not w.operation_running(), timeout=10)
        states = dict(w.compare_states())
        assert sorted(states) == [
            "clash.tap", "down.tap", "games", "games/a.tap", "games/deep", "same.tap", "up.tap",
        ]
        assert states["games/a.tap"] == "unverified"
        assert states["games/deep"] == "not-scanned" and states["games"] == "not-scanned"
        nxt.drop()


def naming_folder(tmp_path, show_hidden):
    folder = tmp_path / "local"
    folder.mkdir()
    for name in ("ok.tap", "a.tap", "A.TAP", "bad?.tap", "junk.bak", ".git"):
        (folder / name).write_bytes(b"x")
    (folder / ".nexplorerignore").write_text("*.bak\n")
    path = tmp_path / "settings.json"
    save(Settings(local_folder=str(folder), show_hidden=show_hidden), path)
    return path


def test_compare_shows_conflict_invalid_ignored_and_hidden_rows_and_transfers_none_of_them(app, tmp_path):
    path = naming_folder(tmp_path, show_hidden=False)
    with opened(app, path) as (w, listener):
        nxt = prepare(app, w, listener, tmp_path, {})
        w.compare()
        assert w.compare_state_texts() == {
            ".git": "Hidden",
            ".nexplorerignore": "Hidden",
            "A.TAP": "Conflict",
            "a.tap": "Conflict",
            "bad?.tap": "Invalid",
            "junk.bak": "Ignored",
            "ok.tap": "Only on Local",
        }
        w.compare_apply()
        assert pump(app, lambda: w.operation_running())
        assert pump(app, lambda: not w.operation_running(), timeout=10)
        assert set(nxt.fs) == {"c:/dest", "c:/dest/ok.tap"}
        nxt.drop()


def test_the_hidden_files_setting_offers_hidden_entries_for_transfer(app, tmp_path):
    path = naming_folder(tmp_path, show_hidden=True)
    with opened(app, path) as (w, listener):
        nxt = prepare(app, w, listener, tmp_path, {})
        w.compare()
        texts = w.compare_state_texts()
        assert texts[".git"] == "Only on Local" and texts[".nexplorerignore"] == "Only on Local"
        nxt.drop()


def test_compare_needs_a_session(app, tmp_path):
    path = local_folder(tmp_path)
    with opened(app, path) as (w, _):
        w.compare()
        assert not w.compare_active()


def test_verify_settles_the_unverified_rows_through_the_next_crc_and_only_when_asked(app, tmp_path):
    path = local_folder(tmp_path)
    (tmp_path / "local" / "other.tap").write_bytes(b"yy")
    with opened(app, path) as (w, listener):
        nxt = prepare(app, w, listener, tmp_path, {**NEXT_FS, "c:/dest/other.tap": b"xx"})
        w.compare()
        states = {name: state for name, state, _, _ in w.compare_rows()}
        assert states["same.tap"] == states["other.tap"] == "unverified"
        assert b"K" not in nxt.commands

        w.compare_verify()
        assert pump(app, lambda: w.operation_running())
        assert pump(app, lambda: not w.operation_running(), timeout=10)
        states = {name: state for name, state, _, _ in w.compare_rows()}
        assert (states["same.tap"], states["other.tap"], states["clash.tap"]) == ("identical", "different", "different")
        assert nxt.commands.count(b"K") == 2
        nxt.drop()


def settled(app, w):
    assert pump(app, lambda: w.operation_running())
    assert pump(app, lambda: not w.operation_running(), timeout=10)


def test_a_nested_row_goes_between_its_own_folders_and_a_folder_row_alone_moves_nothing_below_it(app, tmp_path):
    path = nested_local(tmp_path)
    (tmp_path / "local" / "games" / "new.tap").write_bytes(b"new")
    with opened(app, path) as (w, listener):
        nxt = prepare(app, w, listener, tmp_path, {**TREE_FS, "c:/dest/games/fromnext.tap": b"fn"})
        w.compare()
        w.compare_expand("games")
        assert pump(app, lambda: not w.operation_running(), timeout=10)

        w.compare_transfer("games")  # a folder row on its own: its children stay out
        pump(app, lambda: w.operation_running(), timeout=0.5)
        assert pump(app, lambda: not w.operation_running(), timeout=10)
        assert "c:/dest/games/new.tap" not in nxt.fs and not (tmp_path / "local" / "games" / "fromnext.tap").exists()

        w.compare_transfer("games/new.tap")
        settled(app, w)
        assert nxt.fs["c:/dest/games/new.tap"] == b"new"
        assert "c:/dest/new.tap" not in nxt.fs

        w.compare_apply()
        settled(app, w)
        assert (tmp_path / "local" / "games" / "fromnext.tap").read_bytes() == b"fn"
        assert not (tmp_path / "local" / "fromnext.tap").exists()
        nxt.drop()


def test_rows_are_recomputed_after_apply_so_a_second_apply_sends_nothing_and_expanded_folders_stay(app, tmp_path):
    path = nested_local(tmp_path)
    with opened(app, path) as (w, listener):
        nxt = prepare(app, w, listener, tmp_path, TREE_FS)
        w.compare()
        w.compare_expand("games")
        assert pump(app, lambda: not w.operation_running(), timeout=10)

        w.compare_apply()
        settled(app, w)

        states = dict(w.compare_states())
        assert states["up.tap"] == states["down.tap"] == "unverified"
        assert "games/a.tap" in states  # still expanded
        nxt.commands.clear()
        w.compare_apply()
        pump(app, lambda: w.operation_running(), timeout=0.5)
        assert pump(app, lambda: not w.operation_running(), timeout=10)
        assert not {b"P", b"G"} & set(nxt.commands)
        nxt.drop()


def test_verify_settles_nested_rows_and_state_texts_include_them(app, tmp_path):
    path = nested_local(tmp_path)
    with opened(app, path) as (w, listener):
        nxt = prepare(app, w, listener, tmp_path, {**TREE_FS, "c:/dest/games/deep/z.tap": b"z"})
        w.compare()
        w.compare_expand("games")
        assert pump(app, lambda: not w.operation_running(), timeout=10)
        w.compare_verify()
        settled(app, w)
        states = dict(w.compare_states())
        assert states["games/a.tap"] == "identical"
        texts = w.compare_state_texts()
        assert {"games", "games/a.tap", "games/deep", "up.tap"} <= set(texts)
        nxt.drop()

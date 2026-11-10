"""The Transfer menu entry that sends the bundled sync-wrap.bas to the Next folder shown."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest

from nexplorer.protocol import Listener
from nexplorer.ui.main_window import MainWindow
from tests.conftest import dispose, pump
from tests.fake_next import FakeNext

ENTRY = "Send sync-wrap.bas to the ZX Spectrum Next"
SHIPPED = (Path(__file__).parent.parent / "sync-wrap" / "sync-wrap.bas").read_bytes()
FS = {"c:/games": None, "c:/games/a.txt": b"a"}


@pytest.fixture
def setup(app, tmp_path):
    listener = Listener(host="127.0.0.1", port=0)
    listener.start()
    made = []

    def build(**kwargs):
        w = MainWindow(listener, local_addresses=lambda: [], **kwargs)
        made.append(w)
        w.show()
        return w

    def connect(w, fs=None):
        nxt = FakeNext(listener.port, fs=dict(fs or FS), free_blocks={"C": 2048})
        nxt.connect()
        assert pump(app, lambda: w.next_pane_state() == "connected")
        assert pump(app, lambda: "games" in w.next_pane().names())
        return nxt

    yield build, connect
    for w in made:
        w.close()
        dispose(app, w)
    listener.stop()


def enabled(w) -> bool:
    return w.entry_enabled("Transfer", ENTRY)


def test_the_entry_is_in_the_transfer_menu_and_greyed_until_a_next_is_connected(app, setup):
    build, connect = setup
    w = build()
    assert ENTRY in [text for text, _, _ in w.menu_entries("Transfer")]
    assert not enabled(w)
    nxt = connect(w)
    assert enabled(w)
    nxt.drop()


def into_games(app, w):
    w.next_pane().enter("games")
    assert pump(app, lambda: w.next_pane().path() == "c:/games" and "a.txt" in w.next_pane().names())


def wait_operation(app, w):
    assert pump(app, lambda: w.operation_running())
    assert pump(app, lambda: not w.operation_running(), timeout=10)


def test_the_program_arrives_unchanged_in_the_next_folder_shown(app, setup):
    build, connect = setup
    w = build()
    nxt = connect(w)
    into_games(app, w)
    w.trigger_menu("Transfer", ENTRY)
    wait_operation(app, w)
    assert nxt.fs["c:/games/sync-wrap.bas"] == SHIPPED
    assert "c:/sync-wrap.bas" not in nxt.fs
    nxt.drop()


def test_an_existing_program_is_asked_about_and_cancel_leaves_it_intact(app, setup):
    build, connect = setup
    asked = []

    def cancel(path, remaining):
        asked.append(path)
        return ("cancel", False)

    w = build(confirm_overwrite=cancel)
    nxt = connect(w, {**FS, "c:/games/sync-wrap.bas": b"mine"})
    into_games(app, w)
    w.trigger_menu("Transfer", ENTRY)
    assert pump(app, lambda: bool(asked))
    assert pump(app, lambda: not w.operation_running())
    assert nxt.fs["c:/games/sync-wrap.bas"] == b"mine"
    nxt.drop()


def test_an_existing_program_is_replaced_when_the_user_says_overwrite(app, setup):
    build, connect = setup
    w = build(confirm_overwrite=lambda path, remaining: ("overwrite", False))
    nxt = connect(w, {**FS, "c:/games/sync-wrap.bas": b"mine"})
    into_games(app, w)
    w.trigger_menu("Transfer", ENTRY)
    assert pump(app, lambda: nxt.fs.get("c:/games/sync-wrap.bas") == SHIPPED, timeout=10)
    nxt.drop()


def test_the_entry_is_greyed_when_the_program_cannot_be_found(app, setup):
    build, connect = setup
    w = build(sync_wrap_path=lambda: None)
    nxt = connect(w)
    assert not enabled(w)
    nxt.drop()


def test_the_entry_is_greyed_while_an_operation_runs(app, setup, tmp_path):
    build, connect = setup
    w = build()
    nxt = connect(w)
    into_games(app, w)
    w.trigger_menu("Transfer", ENTRY)
    assert pump(app, lambda: w.operation_running())
    assert not enabled(w)
    assert pump(app, lambda: not w.operation_running(), timeout=10)
    assert enabled(w)
    nxt.drop()

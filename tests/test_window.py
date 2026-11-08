import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from nexplorer.protocol import Listener
from nexplorer.ui.main_window import MainWindow
from tests.conftest import dispose
from tests.fake_next import FakeNext


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def pump(app, predicate, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def window(app):
    listener = Listener(host="127.0.0.1", port=0)
    listener.start()
    w = MainWindow(listener, local_addresses=lambda: [("eth0", "192.168.1.20")])
    w.show()
    yield w, listener
    w.close()
    dispose(app, w)
    listener.stop()


def test_waiting_screen_shows_command_ip_and_config_reminder(app, window):
    w, _ = window
    text = w.next_pane_text()
    assert ".sync5 -l" in text
    assert "192.168.1.20" in text
    assert "nextsync.cfg" in text


def test_connected_pane_shows_address_then_returns_to_waiting(app, window):
    w, listener = window
    nxt = FakeNext(listener.port)
    nxt.connect()
    assert pump(app, lambda: w.next_pane_state() == "connected")
    assert "127.0.0.1" in w.next_pane_text()
    nxt.drop()
    assert pump(app, lambda: w.next_pane_state() == "waiting")
    assert ".sync5 -l" in w.next_pane_text()


def test_next_replacing_a_dropped_one_leaves_the_pane_connected(app, window):
    w, listener = window
    first = FakeNext(listener.port)
    first.connect()
    assert pump(app, lambda: w.next_pane_state() == "connected")
    first.drop()
    second = FakeNext(listener.port)
    end = time.time() + 3
    while second.connect() != b"Listening" and time.time() < end:
        second = FakeNext(listener.port)
        time.sleep(0.02)
    pump(app, lambda: False, timeout=1.0)
    assert w.next_pane_state() == "connected"
    second.drop()


FS = {
    "c:/games": None,
    "c:/games/manic.tap": b"x" * 300,
    "c:/readme.txt": b"hello",
    "m:/tmp.bin": b"zz",
}


def connect_next(app, w, listener, **kwargs):
    nxt = FakeNext(listener.port, fs=FS, free_blocks={"C": 2048, "M": 10}, **kwargs)
    nxt.connect()
    assert pump(app, lambda: w.next_pane_state() == "connected")
    return nxt


def test_next_pane_lists_the_root_of_the_current_drive_once_connected(app, window):
    w, listener = window
    nxt = connect_next(app, w, listener)
    assert pump(app, lambda: w.next_pane().names() == ["games", "readme.txt"])
    assert w.next_pane().path() == "c:/"
    nxt.drop()


def test_next_pane_enters_folders_goes_up_and_takes_a_typed_path(app, window):
    w, listener = window
    nxt = connect_next(app, w, listener)
    pane = w.next_pane()
    assert pump(app, lambda: "games" in pane.names())
    pane.enter("games")
    assert pump(app, lambda: pane.names() == ["manic.tap"])
    assert pane.path() == "c:/games"
    pane.go_up()
    assert pump(app, lambda: pane.path() == "c:/")
    pane.go_to("c:/games")
    assert pump(app, lambda: pane.names() == ["manic.tap"])
    pane.go_to("c:/nope")
    assert pump(app, lambda: pane.error() != "")
    assert pane.path() == "c:/games"
    nxt.drop()


def test_next_pane_switches_drive_and_shows_free_space(app, window):
    w, listener = window
    nxt = connect_next(app, w, listener)
    pane = w.next_pane()
    assert pump(app, lambda: pane.drives() == ["C", "M"] and pane.free_space_text() != "")
    assert pane.free_space_text() == "1.0 MB free"
    pane.switch_drive("M")
    assert pump(app, lambda: pane.names() == ["tmp.bin"])
    assert pane.path() == "m:/"
    assert pump(app, lambda: pane.free_space_text() == "5.0 KB free")
    nxt.drop()


def test_next_pane_goes_back_to_waiting_and_clears_when_the_session_ends(app, window):
    w, listener = window
    nxt = connect_next(app, w, listener)
    assert pump(app, lambda: w.next_pane().names() != [])
    nxt.drop()
    assert pump(app, lambda: w.next_pane_state() == "waiting")
    nxt2 = connect_next(app, w, listener)
    assert pump(app, lambda: w.next_pane().names() == ["games", "readme.txt"])
    nxt2.drop()


@pytest.mark.parametrize("typed", ["a:/", "B:/games", "d:/", "d:/anything", "/games", "games"])
def test_typed_path_on_a_drive_the_next_did_not_report_is_refused_and_never_sent(
    app, window, typed
):
    w, listener = window
    nxt = connect_next(app, w, listener)  # drives C and M only
    pane = w.next_pane()
    assert pump(app, lambda: pane.names() == ["games", "readme.txt"])
    pane.go_to(typed)
    assert pump(app, lambda: pane.error() != "")
    assert pane.path() == "c:/"
    pump(app, lambda: False, timeout=0.3)
    assert nxt.listed == ["c:/"]  # only the first listing, from the bind
    nxt.drop()


def test_typed_path_on_a_reported_drive_is_sent_whatever_its_letter_case(app, window):
    w, listener = window
    nxt = connect_next(app, w, listener)
    pane = w.next_pane()
    assert pump(app, lambda: pane.drives() == ["C", "M"])
    pane.go_to("M:/")
    assert pump(app, lambda: pane.names() == ["tmp.bin"])
    nxt.drop()


def test_cancel_greys_its_button_and_says_it_is_cancelling(app, window, tmp_path):
    w, listener = window
    (tmp_path / "a.bin").write_bytes(b"a" * 512 * 12)
    (tmp_path / "b.bin").write_bytes(b"b" * 10)
    nxt = connect_next(app, w, listener, put_chunk_delay=0.05)  # about 0.6 s for a.bin
    assert pump(app, lambda: "games" in w.next_pane().names())
    w.local_pane().go_to(str(tmp_path))
    assert pump(app, lambda: "a.bin" in w.local_pane().names())
    w.local_pane().select(["a.bin", "b.bin"])

    w.send_selected()
    assert pump(app, w.operation_running)
    assert w.cancel_enabled() and w.cancel_text() == "Cancel"
    w._cancel_button.click()

    assert not w.cancel_enabled()
    assert w.cancel_text() == "Cancelling\u2026"
    assert pump(app, lambda: not w.operation_running(), timeout=5)
    assert w.summary_text().startswith("Cancelled")

    w.send_selected()  # the next operation starts with a fresh button
    assert pump(app, w.operation_running)
    assert w.cancel_enabled() and w.cancel_text() == "Cancel"
    pump(app, lambda: not w.operation_running(), timeout=5)
    nxt.drop()


def test_closing_the_window_makes_the_next_leave(app, window):
    w, listener = window
    nxt = connect_next(app, w, listener)
    w.close()
    assert nxt.ended.wait(timeout=3)  # told to quit, not left polling a dead link


def test_the_quit_button_closes_the_window_and_the_next_leaves(app, window):
    w, listener = window
    nxt = connect_next(app, w, listener)
    assert w.quit_text() == "Quit"
    w._quit_button.click()
    assert not w.isVisible()
    assert nxt.ended.wait(timeout=3)

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from nexplorer.protocol import Listener
from nexplorer.ui.main_window import MainWindow
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

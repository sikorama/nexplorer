"""The window's structure: identical panes, drive selectors, status bar, splitter, waiting card."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import re
from contextlib import contextmanager
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QPushButton

from nexplorer import i18n
from nexplorer.protocol import Listener
from nexplorer.settings import Settings, load, save
from nexplorer.ui.main_window import MainWindow
from tests.conftest import dispose, pump
from tests.fake_next import FakeNext

FS = {"c:/games": None, "c:/games/a.tap": b"x" * 10, "c:/b.txt": b"b" * 5}


@pytest.fixture
def folders(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    (first / "sub").mkdir(parents=True)
    (first / "big.bin").write_bytes(b"x" * 500)
    (first / "small.bin").write_bytes(b"x")
    (second / "other.txt").parent.mkdir()
    (second / "other.txt").write_bytes(b"o")
    return first, second


@contextmanager
def opened(app, settings_path=None, roots=None, **kwargs):
    listener = Listener(host="127.0.0.1", port=0)
    listener.start()
    w = MainWindow(
        listener,
        local_addresses=lambda: [("eth0", "192.168.1.20")],
        settings_path=settings_path,
        local_roots=roots or (lambda: []),
        **kwargs,
    )
    w.show()
    try:
        yield w, listener
    finally:
        w.close()
        dispose(app, w)
        listener.stop()


def connect(app, w, listener):
    nxt = FakeNext(listener.port, fs=FS, free_blocks={"C": 2048})
    nxt.connect()
    assert pump(app, lambda: w.next_pane_state() == "connected")
    assert pump(app, lambda: w.next_pane().names() == ["games", "b.txt"])
    return nxt


def list_top(w, pane) -> int:
    return pane.list_view().mapTo(w, QPoint(0, 0)).y()


def test_the_two_panes_line_up_whether_the_next_is_waiting_or_connected(app, folders):
    first, _ = folders
    with opened(app, roots=lambda: [("first", str(first))]) as (w, listener):
        assert pump(app, lambda: w.local_pane().names() != [])
        assert list_top(w, w.local_pane()) == list_top(w, w.next_pane())
        nxt = connect(app, w, listener)
        assert list_top(w, w.local_pane()) == list_top(w, w.next_pane())
        assert w.local_pane().list_view().height() == w.next_pane().list_view().height()
        nxt.drop()


def test_both_panes_sort_the_same_way(app, folders):
    first, _ = folders
    with opened(app) as (w, listener):
        nxt = connect(app, w, listener)
        w.local_pane().go_to(str(first))
        assert pump(app, lambda: w.local_pane().path() == str(first) and w.local_pane().names())
        for pane in (w.local_pane(), w.next_pane()):
            pane.sort_by("size")
            assert pane.sort() == ("size", False)
            pane.sort_by("size")
            assert pane.sort() == ("size", True)
        assert w.local_pane().names() == ["sub", "big.bin", "small.bin"]
        nxt.drop()


def test_the_local_drive_selector_lists_the_roots_and_switches_folder(app, folders):
    first, second = folders
    roots = lambda: [("first", str(first)), ("second", str(second))]
    with opened(app, roots=roots) as (w, _):
        pane = w.local_pane()
        pane.open_drive_selector()
        assert pane.drives() == ["first", "second"]
        pane.switch_drive("second")
        assert pump(app, lambda: pane.path() == str(second) and pane.names() == ["other.txt"])
        assert pane.free_space_text().endswith("free")
        assert pane.drives() == ["first", "second"]


def test_the_local_roots_are_read_again_each_time_the_selector_opens(app, folders):
    first, second = folders
    found = [[("first", str(first))]]
    with opened(app, roots=lambda: found[0]) as (w, _):
        pane = w.local_pane()
        pane.open_drive_selector()
        assert pane.drives() == ["first"]
        found[0] = [("first", str(first)), ("card", str(second))]
        pane.open_drive_selector()
        assert pane.drives() == ["first", "card"]


def test_the_selection_summary_is_in_the_status_bar(app, folders):
    first, _ = folders
    with opened(app, roots=lambda: [("first", str(first))]) as (w, _):
        pane = w.local_pane()
        pane.go_to(str(first))
        assert pump(app, lambda: pane.path() == str(first) and pane.names())
        pane.select(["big.bin", "small.bin"])
        assert w.selection_summary() == "2 items, 501 B"
        pane.select(["big.bin"])
        assert w.selection_summary() == "1 item, 500 B"
        pane.select([])
        assert w.selection_summary() == ""


def test_the_connection_and_the_dot_warning_are_in_the_status_bar(app, folders):
    with opened(app) as (w, listener):
        assert "127.0.0.1" not in w.connection_text()
        nxt = FakeNext(listener.port, fs=FS, free_blocks={"C": 2048}, version="5.1.0")
        nxt.connect()
        assert pump(app, lambda: w.next_pane_state() == "connected")
        assert "127.0.0.1" in w.connection_text()
        assert pump(app, lambda: "5.9.2" in w.dot_notice())
        assert w.status_bar_shows_dot_notice()
        nxt.drop()
        assert pump(app, lambda: w.next_pane_state() == "waiting")
        assert "127.0.0.1" not in w.connection_text() and w.dot_notice() == ""


def test_progress_and_cancel_stay_visible_during_a_transfer(app, folders):
    first, _ = folders
    with opened(app, roots=lambda: [("first", str(first))]) as (w, listener):
        nxt = connect(app, w, listener)
        w.local_pane().go_to(str(first))
        assert pump(app, lambda: w.local_pane().path() == str(first) and w.local_pane().names())
        w.local_pane().select(["big.bin"])
        assert not w.progress_visible()
        w.send_selected()
        assert w.progress_visible() and w.cancel_enabled()
        assert pump(app, lambda: not w.operation_running(), timeout=5)
        assert not w.progress_visible()
        nxt.drop()


def test_the_waiting_card_shows_addresses_command_and_config_reminder(app):
    with opened(app) as (w, _):
        text = w.waiting_card_text()
        assert "192.168.1.20" in text and ".sync5 -l" in text and "nextsync.cfg" in text


def test_the_waiting_card_advises_drive_d_and_sync_wrap(app):
    with opened(app) as (w, _):
        text = w.waiting_card_text()
        assert "D:" in text and "sync-wrap.bas" in text


def test_the_waiting_card_has_no_button(app):
    with opened(app) as (w, _):
        assert w.waiting_card().findChildren(QPushButton) == []


def test_the_next_toolbar_is_greyed_while_waiting_and_not_hidden(app, folders):
    with opened(app) as (w, listener):
        assert w.next_pane().controls_visible() and not w.next_pane().controls_enabled()
        assert w.local_pane().controls_enabled()
        nxt = connect(app, w, listener)
        assert w.next_pane().controls_enabled()
        nxt.drop()
        assert pump(app, lambda: w.next_pane_state() == "waiting")
        assert not w.next_pane().controls_enabled() and w.next_pane().controls_visible()


def test_default_and_minimum_size(app):
    with opened(app) as (w, _):
        assert (w.minimumWidth(), w.minimumHeight()) == (800, 450)
        assert w.size().width() >= 800 and w.size().height() >= 450


def test_a_new_window_opens_at_1100_by_650(app):
    listener = Listener(host="127.0.0.1", port=0)
    w = MainWindow(listener, local_addresses=lambda: [], local_roots=lambda: [])
    try:
        assert (w.width(), w.height()) == (1100, 650)
    finally:
        dispose(app, w)


def test_the_splitter_position_is_applied_and_persisted(app, tmp_path):
    path = tmp_path / "settings.json"
    save(Settings(splitter=(300, 700)), path)
    with opened(app, path) as (w, _):
        left, right = w.splitter_sizes()
        assert left < right
        w.set_splitter_sizes([700, 300])
    assert load(path).splitter[0] > load(path).splitter[1]
    with opened(app, path) as (w, _):
        left, right = w.splitter_sizes()
        assert left > right


def test_no_interface_string_says_the_next_or_on_next_and_french_is_translated():
    root = Path(__file__).parent.parent / "nexplorer"
    texts = set()
    for source in root.rglob("*.py"):
        texts |= set(re.findall(r"tr\(\s*[\"']([^\"']+)[\"']", source.read_text(encoding="utf-8")))
    about_next = {t for t in texts if "Next" in t}
    assert about_next
    french = json.loads((root / "locales" / "fr.json").read_text(encoding="utf-8"))
    for text in about_next:
        assert not re.search(r"\b(the|on|from|a|No) Next\b", text) or "ZX Spectrum Next" in text, text
        assert re.search(r"\bNext\b", text.replace("ZX Spectrum Next", "")) is None, text
        assert text in french, text
        assert "la Next" not in french[text] and "une Next" not in french[text], text

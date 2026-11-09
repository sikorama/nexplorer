"""The menu bar, the shortcuts and the context menus: one action each, applied to the active pane."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton

from nexplorer.protocol import Listener
from nexplorer.ui.main_window import MainWindow
from tests.conftest import dispose, pump
from tests.fake_next import FakeNext
from tests.test_window import FS, Prompts


@pytest.fixture
def window(app, tmp_path):
    (tmp_path / "local.txt").write_bytes(b"l")
    listener = Listener(host="127.0.0.1", port=0)
    listener.start()
    prompts = Prompts()
    from nexplorer.settings import Settings, save

    path = tmp_path / "settings.json"
    save(Settings(local_folder=str(tmp_path)), path)
    asked = []
    w = MainWindow(
        listener,
        local_addresses=lambda: [],
        ask_name=prompts.ask_name,
        confirm_delete=prompts.confirm_delete,
        settings_path=path,
        ask_settings=lambda current: asked.append(current),
        show_about=lambda: asked.append("about"),
    )
    w.prompts, w.asked_dialogs = prompts, asked
    w.show()
    w.activateWindow()
    yield w, listener
    w.close()
    dispose(app, w)
    listener.stop()


def connected(app, w, listener, **kwargs):
    nxt = FakeNext(listener.port, fs=FS, free_blocks={"C": 2048}, **kwargs)
    nxt.connect()
    assert pump(app, lambda: w.next_pane_state() == "connected")
    assert pump(app, lambda: "readme.txt" in w.next_pane().names())
    return nxt


def focus(app, w, side):
    pane = w.next_pane() if side == "next" else w.local_pane()
    pane.list_view().setFocus()
    pump(app, lambda: w.active_pane() == side, timeout=0.5)


def entry(entries, text):
    return next(e for e in entries if e[0] == text)


def test_the_menu_bar_has_five_menus_with_their_entries_and_shortcuts(app, window):
    w, _ = window
    assert w.menu_titles() == ["File", "Edit", "Transfer", "View", "Help"]
    expected = {
        "File": [("New folder", "Ctrl+Shift+N"), ("Rename", "F2"), ("Delete", "Del"), ("Settings", ""), ("Quit", "Ctrl+Q")],
        "Edit": [("Copy", "Ctrl+C"), ("Cut", "Ctrl+X"), ("Paste", "Ctrl+V"), ("Select all", "Ctrl+A")],
        "Transfer": [("Send", ""), ("Receive", ""), ("Compare", ""), ("Disconnect", "")],
        "View": [("Show hidden files", ""), ("Sort by", ""), ("Refresh", "Ctrl+R")],
        "Help": [("About", "")],
    }
    for menu, items in expected.items():
        assert [(t, s) for t, s, _ in w.menu_entries(menu)] == items


def test_the_former_action_buttons_are_gone(app, window):
    w, _ = window
    labels = {b.text() for b in w.findChildren(QPushButton)}
    assert not labels & {"Send \u2192", "\u2190 Receive", "New folder", "Rename", "Delete", "Paste", "Cut", "Settings", "Quit"}


def test_a_pane_becomes_active_when_it_gets_focus_and_is_marked(app, window):
    w, listener = window
    nxt = connected(app, w, listener)
    assert w.active_pane() == "local" and w.local_pane().is_active()
    focus(app, w, "next")
    assert w.active_pane() == "next" and w.next_pane().is_active() and not w.local_pane().is_active()
    focus(app, w, "local")
    assert w.active_pane() == "local" and w.local_pane().is_active() and not w.next_pane().is_active()
    w.next_pane().address_field().setFocus()  # any control of a pane counts
    assert pump(app, lambda: w.active_pane() == "next", timeout=0.5)
    nxt.drop()


def test_actions_follow_the_active_pane(app, window):
    w, listener = window
    nxt = connected(app, w, listener)
    w.next_pane().select(["readme.txt"])
    focus(app, w, "next")
    assert entry(w.menu_entries("File"), "Delete")[2]
    focus(app, w, "local")  # the Local side has no such action yet
    assert not entry(w.menu_entries("File"), "Delete")[2]
    assert entry(w.menu_entries("View"), "Refresh")[2]
    nxt.drop()


def test_entries_are_greyed_without_a_session(app, window):
    w, _ = window
    w.activate_pane("next")
    enabled = {t for m in ("File", "Edit", "Transfer") for t, _, on in w.menu_entries(m) if on}
    assert enabled == {"Settings", "Quit"}


def test_entries_follow_the_selection_and_the_dot(app, window):
    w, listener = window
    nxt = connected(app, w, listener, version="5.1.0")
    focus(app, w, "next")
    assert pump(app, w.dot_version_known)
    pane = w.next_pane()
    assert entry(w.menu_entries("File"), "New folder")[2]
    assert not entry(w.menu_entries("File"), "Delete")[2]  # nothing selected
    pane.select(["readme.txt"])
    file_menu = w.menu_entries("File")
    assert entry(file_menu, "Delete")[2] and entry(file_menu, "Rename")[2]
    edit = w.menu_entries("Edit")
    assert not entry(edit, "Copy")[2] and not entry(edit, "Paste")[2]  # an old dot cannot copy
    pane.select(["readme.txt", "games"])
    assert not entry(w.menu_entries("File"), "Rename")[2]
    nxt.drop()


def test_menu_entries_run_the_action_on_the_next_pane(app, window):
    w, listener = window
    nxt = connected(app, w, listener)
    focus(app, w, "next")
    pane = w.next_pane()
    w.prompts.name = "saves"
    w.trigger_menu("File", "New folder")
    assert pump(app, lambda: "c:/saves" in nxt.fs and "saves" in pane.names())
    pane.select(["readme.txt"])
    w.prompts.name = "notes.txt"
    w.trigger_menu("File", "Rename")
    assert pump(app, lambda: "c:/notes.txt" in nxt.fs and "notes.txt" in pane.names())
    assert w.prompts.asked[-1] == ("Rename", "readme.txt")
    pane.select(["notes.txt"])
    w.trigger_menu("Edit", "Copy")
    pane.enter("games")
    assert pump(app, lambda: pane.names() == ["manic.tap"])
    w.trigger_menu("Edit", "Paste")
    assert pump(app, lambda: "c:/games/notes.txt" in nxt.fs and "notes.txt" in pane.names())
    pane.select(["notes.txt"])
    w.trigger_menu("Edit", "Cut")
    w.trigger_menu("File", "Delete")
    assert pump(app, lambda: "c:/games/notes.txt" not in nxt.fs)
    assert "ZX Spectrum Next" in w.prompts.confirmations[0]
    nxt.drop()


def test_shortcuts_run_the_action_on_the_active_pane(app, window):
    w, listener = window
    nxt = connected(app, w, listener)
    focus(app, w, "next")
    tree, pane = w.next_pane().list_view(), w.next_pane()
    w.prompts.name = "saves"
    QTest.keyClick(tree, Qt.Key_N, Qt.ControlModifier | Qt.ShiftModifier)
    assert pump(app, lambda: "c:/saves" in nxt.fs and "saves" in pane.names())
    pane.select(["readme.txt"])
    w.prompts.name = "notes.txt"
    QTest.keyClick(tree, Qt.Key_F2)
    assert pump(app, lambda: "c:/notes.txt" in nxt.fs and "notes.txt" in pane.names())
    pane.select(["notes.txt"])
    QTest.keyClick(tree, Qt.Key_X, Qt.ControlModifier)
    pane.enter("games")
    assert pump(app, lambda: pane.names() == ["manic.tap"])
    QTest.keyClick(tree, Qt.Key_V, Qt.ControlModifier)
    assert pump(app, lambda: "c:/games/notes.txt" in nxt.fs and "notes.txt" in pane.names())
    pane.select(["notes.txt"])
    QTest.keyClick(tree, Qt.Key_C, Qt.ControlModifier)
    assert w.entry_enabled("Edit", "Paste")
    QTest.keyClick(tree, Qt.Key_Delete)
    assert pump(app, lambda: "c:/games/notes.txt" not in nxt.fs)
    nxt.drop()


def test_a_shortcut_does_nothing_when_the_local_pane_is_active(app, window):
    w, listener = window
    nxt = connected(app, w, listener)
    w.next_pane().select(["readme.txt"])
    focus(app, w, "local")
    QTest.keyClick(w.local_pane().list_view(), Qt.Key_Delete)
    assert w.prompts.confirmations == []
    nxt.drop()


def test_settings_quit_and_about_are_reachable_from_the_menus(app, window):
    w, _ = window
    w.trigger_menu("File", "Settings")
    w.trigger_menu("Help", "About")
    assert w.asked_dialogs == [w._settings, "about"]
    w.trigger_menu("File", "Quit")
    assert not w.isVisible()


def test_view_menu_toggles_hidden_files_sorts_and_refreshes_the_active_pane(app, window, tmp_path):
    (tmp_path / ".dot").write_bytes(b"d")
    (tmp_path / "zz.txt").write_bytes(b"z" * 100)
    w, _ = window
    pane = w.local_pane()
    focus(app, w, "local")
    pane.go_to(str(tmp_path))
    assert pump(app, lambda: "zz.txt" in pane.names())
    assert ".dot" not in pane.names()
    w.trigger_menu("View", "Show hidden files")
    assert ".dot" in pane.names()
    assert w.entry_checked("View", "Show hidden files")
    w.trigger_menu("View", "Sort by/Size")
    assert pane.sort() == ("size", False)
    (tmp_path / "late.txt").write_bytes(b"x")
    w.trigger_menu("View", "Refresh")
    assert pump(app, lambda: "late.txt" in pane.names())


def test_select_all_selects_the_rows_of_the_active_pane(app, window):
    w, listener = window
    nxt = connected(app, w, listener)
    focus(app, w, "next")
    w.trigger_menu("Edit", "Select all")
    assert w.next_pane().selected_names() == ["games", "readme.txt"]
    nxt.drop()


def test_transfer_menu_sends_receives_compares_and_disconnects(app, window, tmp_path):
    w, listener = window
    nxt = connected(app, w, listener)
    pane = w.local_pane()
    assert pump(app, lambda: "local.txt" in pane.names())
    pane.select(["local.txt"])
    w.trigger_menu("Transfer", "Send")
    assert pump(app, lambda: "c:/local.txt" in nxt.fs)
    assert pump(app, lambda: not w.operation_running())
    w.next_pane().select(["readme.txt"])
    w.trigger_menu("Transfer", "Receive")
    assert pump(app, lambda: (tmp_path / "readme.txt").exists())
    assert pump(app, lambda: not w.operation_running())
    w.trigger_menu("Transfer", "Compare")
    assert w.compare_active()
    w.compare_back()
    w.trigger_menu("Transfer", "Disconnect")
    assert nxt.ended.wait(timeout=5)


def test_transfer_entries_are_greyed_while_an_operation_runs(app, window):
    w, listener = window
    nxt = connected(app, w, listener)
    w._busy = True
    w._update_actions()
    assert not any(on for text, _, on in w.menu_entries("Transfer") if text != "Disconnect")
    assert not entry(w.menu_entries("File"), "New folder")[2]
    w._busy = False
    w._update_actions()
    nxt.drop()


def test_context_menu_on_a_row_offers_the_selection_actions(app, window):
    w, listener = window
    nxt = connected(app, w, listener)
    w.next_pane().select(["games"])
    entries = w.context_entries("next", "readme.txt")  # an unselected row is selected first
    assert w.next_pane().selected_names() == ["readme.txt"]
    assert [t for t, _, _ in entries] == ["Copy", "Cut", "Paste", "Rename", "Delete"]
    assert entry(entries, "Copy")[1] == "Ctrl+C" and entry(entries, "Rename")[1] == "F2"
    assert entry(entries, "Copy")[2] and entry(entries, "Rename")[2] and not entry(entries, "Paste")[2]
    assert w.active_pane() == "next"
    nxt.drop()


def test_context_menu_on_a_selected_row_keeps_the_whole_selection(app, window):
    w, listener = window
    nxt = connected(app, w, listener)
    w.next_pane().select(["games", "readme.txt"])
    entries = w.context_entries("next", "readme.txt")
    assert w.next_pane().selected_names() == ["games", "readme.txt"]
    assert not entry(entries, "Rename")[2] and entry(entries, "Delete")[2]
    nxt.drop()


def test_context_menu_on_empty_space_offers_what_needs_no_selection(app, window):
    w, listener = window
    nxt = connected(app, w, listener)
    w.next_pane().select(["games"])
    entries = w.context_entries("next", None)
    assert w.next_pane().selected_names() == []
    assert [t for t, _, _ in entries] == ["New folder", "Paste", "Select all", "Refresh"]
    assert entry(entries, "New folder")[2] and entry(entries, "Select all")[2]
    w.trigger_context("next", None, "New folder")
    w.prompts.name = None
    assert w.prompts.asked[-1][0] == "New folder"
    nxt.drop()


def test_context_menu_entry_runs_the_action_on_the_clicked_pane(app, window):
    w, listener = window
    nxt = connected(app, w, listener)
    focus(app, w, "local")
    w.prompts.confirm = True
    w.trigger_context("next", "readme.txt", "Delete")
    assert pump(app, lambda: "c:/readme.txt" not in nxt.fs)
    nxt.drop()

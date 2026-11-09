"""Local pane: the shared actions (menu, shortcut, context menu) and the drag inside the pane."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from nexplorer import local_ops
from nexplorer.protocol import Listener
from nexplorer.settings import Settings, save
from nexplorer.ui.main_window import MainWindow
from tests.conftest import dispose, pump
from tests.fake_next import FakeNext
from tests.test_window import FS, Prompts


class Trash:
    def __init__(self):
        self.fail = False
        self.sent = []

    def __call__(self, path):
        if self.fail:
            raise OSError("trash unavailable")
        self.sent.append(path)
        local_ops.delete_path(path)


class Permanent:
    def __init__(self):
        self.answer = True
        self.asked = []

    def __call__(self, message):
        self.asked.append(message)
        return self.answer


@pytest.fixture
def window(app, tmp_path):
    folder = tmp_path / "local"
    (folder / "dest").mkdir(parents=True)
    (folder / "a.txt").write_bytes(b"a")
    (folder / "b.txt").write_bytes(b"b")
    listener = Listener(host="127.0.0.1", port=0)
    listener.start()
    prompts, trash, permanent = Prompts(), Trash(), Permanent()
    path = tmp_path / "settings.json"
    save(Settings(local_folder=str(folder)), path)
    w = MainWindow(
        listener,
        local_addresses=lambda: [],
        ask_name=prompts.ask_name,
        confirm_delete=prompts.confirm_delete,
        confirm_permanent=permanent,
        trash=trash,
        settings_path=path,
    )
    w.prompts, w.trash, w.permanent, w.folder = prompts, trash, permanent, folder
    w.show()
    w.activateWindow()
    assert pump(app, lambda: "a.txt" in w.local_pane().names())
    w.local_pane().list_view().setFocus()
    assert pump(app, lambda: w.active_pane() == "local", timeout=0.5)
    yield w, listener
    w.close()
    dispose(app, w)
    listener.stop()


def idle(app, w):
    assert pump(app, lambda: not w.operation_running())
    assert pump(app, lambda: not w.local_pane().is_loading())


def test_new_folder_and_rename_on_local_through_the_menu(app, window):
    w, _ = window
    w.prompts.name = "saves"
    w.trigger_menu("File", "New folder")
    assert pump(app, lambda: (w.folder / "saves").is_dir() and "saves" in w.local_pane().names())
    idle(app, w)
    w.local_pane().select(["a.txt"])
    w.prompts.name = "z.txt"
    w.trigger_menu("File", "Rename")
    assert pump(app, lambda: (w.folder / "z.txt").exists() and "z.txt" in w.local_pane().names())
    assert w.prompts.asked[-1] == ("Rename", "a.txt")


def test_an_unsafe_name_is_refused_without_touching_the_disk(app, window):
    w, _ = window
    w.prompts.name = "../evil"
    w.trigger_menu("File", "New folder")
    w.local_pane().select(["a.txt"])
    w.trigger_menu("File", "Rename")
    pump(app, lambda: False, timeout=0.2)
    assert not w.operation_running()
    assert not (w.folder.parent / "evil").exists() and (w.folder / "a.txt").exists()
    assert "Invalid name" in w.summary_text()


def test_local_actions_follow_the_selection_and_the_clipboard(app, window):
    w, _ = window
    assert w.entry_enabled("File", "New folder")
    assert not w.entry_enabled("File", "Rename") and not w.entry_enabled("File", "Delete")
    assert not w.entry_enabled("Edit", "Copy") and not w.entry_enabled("Edit", "Paste")
    w.local_pane().select(["a.txt", "b.txt"])
    assert w.entry_enabled("File", "Delete") and w.entry_enabled("Edit", "Copy")
    assert not w.entry_enabled("File", "Rename")
    w.local_pane().select(["a.txt"])
    assert w.entry_enabled("File", "Rename")
    w.trigger_menu("Edit", "Copy")
    assert w.entry_enabled("Edit", "Paste")


def test_delete_asks_in_terms_of_the_trash_with_cancel_as_the_safe_answer_then_trashes(app, window):
    w, _ = window
    w.local_pane().select(["a.txt", "b.txt"])
    w.prompts.confirm = False
    w.trigger_menu("File", "Delete")
    assert "trash" in w.prompts.confirmations[0] and "2" in w.prompts.confirmations[0]
    assert w.trash.sent == [] and (w.folder / "a.txt").exists()
    w.prompts.confirm = True
    w.trigger_menu("File", "Delete")
    assert pump(app, lambda: w.local_pane().names() == ["dest"])
    assert sorted(os.path.basename(p) for p in w.trash.sent) == ["a.txt", "b.txt"]
    assert w.permanent.asked == []


def test_when_the_trash_fails_permanent_deletion_is_offered_and_cancel_keeps_everything(app, window):
    w, _ = window
    w.trash.fail = True
    w.local_pane().select(["a.txt"])
    w.permanent.answer = False
    w.trigger_menu("File", "Delete")
    assert len(w.permanent.asked) == 1 and "a.txt" in w.permanent.asked[0]
    pump(app, lambda: False, timeout=0.2)
    assert (w.folder / "a.txt").exists() and not w.operation_running()
    assert "a.txt" in w.summary_text()
    w.permanent.answer = True
    idle(app, w)
    w.local_pane().select(["a.txt"])
    w.trigger_menu("File", "Delete")
    assert pump(app, lambda: not (w.folder / "a.txt").exists() and "a.txt" not in w.local_pane().names())
    assert (w.folder / "b.txt").exists()


def test_cut_then_paste_inside_local_moves_and_clears_the_clipboard(app, window):
    w, _ = window
    pane = w.local_pane()
    pane.select(["a.txt"])
    w.trigger_menu("Edit", "Cut")
    pane.enter("dest")
    assert pump(app, lambda: pane.path() == str(w.folder / "dest"))
    w.trigger_menu("Edit", "Paste")
    assert pump(app, lambda: "a.txt" in pane.names())
    assert not (w.folder / "a.txt").exists() and (w.folder / "dest" / "a.txt").read_bytes() == b"a"
    idle(app, w)
    assert not w.entry_enabled("Edit", "Paste")


def test_copy_then_paste_duplicates_and_keeps_the_clipboard(app, window):
    w, _ = window
    pane = w.local_pane()
    pane.select(["a.txt"])
    w.trigger_menu("Edit", "Copy")
    pane.enter("dest")
    assert pump(app, lambda: pane.path() == str(w.folder / "dest"))
    w.trigger_menu("Edit", "Paste")
    assert pump(app, lambda: "a.txt" in pane.names())
    idle(app, w)
    assert (w.folder / "a.txt").exists() and w.entry_enabled("Edit", "Paste")


def test_a_paste_never_overwrites_and_reports_the_entry(app, window):
    w, _ = window
    pane = w.local_pane()
    (w.folder / "dest" / "a.txt").write_bytes(b"old")
    pane.select(["a.txt"])
    w.trigger_menu("Edit", "Cut")
    pane.enter("dest")
    assert pump(app, lambda: pane.path() == str(w.folder / "dest"))
    w.trigger_menu("Edit", "Paste")
    assert pump(app, lambda: "a.txt: " in w.summary_text())
    assert (w.folder / "dest" / "a.txt").read_bytes() == b"old" and (w.folder / "a.txt").exists()
    idle(app, w)
    assert w.entry_enabled("Edit", "Paste")  # a failed move can be retried


def test_shortcuts_and_context_menu_drive_the_local_pane(app, window):
    w, _ = window
    tree, pane = w.local_pane().list_view(), w.local_pane()
    pane.select(["a.txt"])
    w.prompts.name = "q.txt"
    QTest.keyClick(tree, Qt.Key_F2)
    assert pump(app, lambda: "q.txt" in pane.names())
    idle(app, w)
    pane.select(["b.txt"])
    QTest.keyClick(tree, Qt.Key_Delete)
    assert pump(app, lambda: "b.txt" not in pane.names())
    entries = w.context_entries("local", "q.txt")
    assert [t for t, _, _ in entries] == ["Copy", "Cut", "Paste", "Rename", "Delete"]
    assert all(on for text, _, on in entries if text != "Paste")
    w.trigger_context("local", "q.txt", "Delete")
    assert pump(app, lambda: "q.txt" not in pane.names())


def drag_local(pane, names, target, modifiers=Qt.NoModifier):
    pane.select(names)
    mime = pane.drag_mime()
    view = pane.list_view().viewport()
    point = QPoint(view.width() - 2, view.height() - 2) if target is None else pane.row_center(target)
    for kind in (QDragEnterEvent, QDragMoveEvent, QDropEvent):
        QApplication.sendEvent(view, kind(point, Qt.CopyAction, mime, Qt.LeftButton, modifiers))


def test_dragging_local_entries_onto_a_local_folder_moves_them(app, window):
    w, _ = window
    drag_local(w.local_pane(), ["a.txt", "b.txt"], "dest")
    assert pump(app, lambda: w.local_pane().names() == ["dest"])
    assert sorted(os.listdir(w.folder / "dest")) == ["a.txt", "b.txt"]


def test_shift_drag_copies(app, window):
    w, _ = window
    drag_local(w.local_pane(), ["a.txt"], "dest", Qt.ShiftModifier)
    assert pump(app, lambda: (w.folder / "dest" / "a.txt").exists() and not w.operation_running())
    assert (w.folder / "a.txt").exists()


def test_a_local_drag_on_a_file_or_empty_space_does_nothing(app, window):
    w, _ = window
    drag_local(w.local_pane(), ["a.txt"], "b.txt")
    drag_local(w.local_pane(), ["a.txt"], None)
    drag_local(w.local_pane(), ["dest"], "dest")  # onto itself
    pump(app, lambda: False, timeout=0.3)
    assert sorted(os.listdir(w.folder)) == ["a.txt", "b.txt", "dest"] and os.listdir(w.folder / "dest") == []


def test_a_local_drag_is_not_taken_by_the_next_pane(app, window):
    w, listener = window
    nxt = FakeNext(listener.port, fs=FS, free_blocks={"C": 2048})
    nxt.connect()
    assert pump(app, lambda: w.next_pane_state() == "connected")
    assert pump(app, lambda: "games" in w.next_pane().names())
    w.local_pane().select(["a.txt"])
    mime = w.local_pane().drag_mime()
    pane = w.next_pane()
    view = pane.list_view().viewport()
    for kind in (QDragEnterEvent, QDragMoveEvent, QDropEvent):
        QApplication.sendEvent(view, kind(pane.row_center("games"), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
    pump(app, lambda: False, timeout=0.3)
    assert not w.operation_running() and sorted(nxt.fs) == sorted(k.lower() for k in FS)
    nxt.drop()


def test_the_next_delete_confirmation_says_the_deletion_is_permanent(app, window):
    w, listener = window
    nxt = FakeNext(listener.port, fs=FS, free_blocks={"C": 2048})
    nxt.connect()
    assert pump(app, lambda: "games" in w.next_pane().names())
    w.next_pane().list_view().setFocus()
    assert pump(app, lambda: w.active_pane() == "next", timeout=0.5)
    w.next_pane().select(["readme.txt"])
    w.prompts.confirm = False
    w.trigger_menu("File", "Delete")
    assert "permanent" in w.prompts.confirmations[0]
    nxt.drop()

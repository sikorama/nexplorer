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


class Prompts:
    """Stands in for the dialogs: scripted answers, and what the window asked."""

    def __init__(self):
        self.name = None  # what the user types in the name prompt; None = cancel
        self.confirm = True
        self.asked = []
        self.confirmations = []

    def ask_name(self, title, initial=""):
        self.asked.append((title, initial))
        return self.name

    def confirm_delete(self, message):
        self.confirmations.append(message)
        return self.confirm


@pytest.fixture
def window(app):
    listener = Listener(host="127.0.0.1", port=0)
    listener.start()
    prompts = Prompts()
    w = MainWindow(
        listener,
        local_addresses=lambda: [("eth0", "192.168.1.20")],
        ask_name=prompts.ask_name,
        confirm_delete=prompts.confirm_delete,
    )
    w.prompts = prompts
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


def drop_files(pane, paths, target=None):
    """Drop external files on the Next pane's list; `target` is a row name, else empty space."""
    from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
    from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
    view = pane.list_view().viewport()
    if target is None:
        point = QPoint(view.width() - 2, view.height() - 2)
    else:
        point = pane.row_center(target)
    for kind in (QDragEnterEvent, QDragMoveEvent, QDropEvent):
        event = kind(point, Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(view, event)


def test_dropping_external_files_on_the_next_pane_sends_them_into_the_shown_folder(
    app, window, tmp_path
):
    w, listener = window
    (tmp_path / "a.bin").write_bytes(b"a" * 40)
    nxt = connect_next(app, w, listener)
    pane = w.next_pane()
    assert pump(app, lambda: "games" in pane.names())
    drop_files(pane, [str(tmp_path / "a.bin")])
    assert pump(app, lambda: nxt.fs.get("c:/a.bin") == b"a" * 40, timeout=5)
    assert pump(app, lambda: not w.operation_running())
    nxt.drop()


def test_dropping_on_a_next_subfolder_sends_into_that_subfolder(app, window, tmp_path):
    w, listener = window
    (tmp_path / "a.bin").write_bytes(b"a" * 40)
    nxt = connect_next(app, w, listener)
    pane = w.next_pane()
    assert pump(app, lambda: "games" in pane.names())
    drop_files(pane, [str(tmp_path / "a.bin")], target="games")
    assert pump(app, lambda: nxt.fs.get("c:/games/a.bin") == b"a" * 40, timeout=5)
    assert pump(app, lambda: not w.operation_running())
    assert "c:/a.bin" not in nxt.fs
    nxt.drop()


def test_dropping_on_a_next_file_row_sends_into_the_shown_folder(app, window, tmp_path):
    w, listener = window
    (tmp_path / "a.bin").write_bytes(b"a" * 40)
    nxt = connect_next(app, w, listener)
    pane = w.next_pane()
    assert pump(app, lambda: "readme.txt" in pane.names())
    drop_files(pane, [str(tmp_path / "a.bin")], target="readme.txt")
    assert pump(app, lambda: nxt.fs.get("c:/a.bin") == b"a" * 40, timeout=5)
    assert nxt.fs["c:/readme.txt"] == b"hello"
    nxt.drop()


def drop_next_entries_on_local(w, names):
    """Start a drag of `names` from the Next pane and drop it on the Local pane's empty space."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent

    w.next_pane().select(names)
    mime = w.next_pane().drag_mime()
    view = w.local_pane().list_view().viewport()
    point = QPoint(view.width() - 2, view.height() - 2)
    for kind in (QDragEnterEvent, QDragMoveEvent, QDropEvent):
        event = kind(point, Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(view, event)


def test_dragging_next_entries_onto_the_local_pane_receives_them_into_the_shown_folder(
    app, window, tmp_path
):
    w, listener = window
    nxt = connect_next(app, w, listener)
    assert pump(app, lambda: "readme.txt" in w.next_pane().names())
    w.local_pane().go_to(str(tmp_path))
    assert pump(app, lambda: w.local_pane().path() == str(tmp_path))
    drop_next_entries_on_local(w, ["readme.txt"])
    assert pump(app, lambda: (tmp_path / "readme.txt").exists() and not w.operation_running(), timeout=5)
    assert (tmp_path / "readme.txt").read_bytes() == b"hello"
    nxt.drop()


def test_a_drop_during_an_operation_is_refused_in_both_directions(app, window, tmp_path):
    w, listener = window
    (tmp_path / "a.bin").write_bytes(b"a" * 512 * 12)
    (tmp_path / "b.bin").write_bytes(b"b" * 10)
    nxt = connect_next(app, w, listener, put_chunk_delay=0.05)
    pane = w.next_pane()
    assert pump(app, lambda: "readme.txt" in pane.names())
    w.local_pane().go_to(str(tmp_path))
    assert pump(app, lambda: w.local_pane().path() == str(tmp_path))
    drop_files(pane, [str(tmp_path / "a.bin")])
    assert pump(app, w.operation_running)
    drop_files(pane, [str(tmp_path / "b.bin")])
    drop_next_entries_on_local(w, ["readme.txt"])
    assert pump(app, lambda: not w.operation_running(), timeout=5)
    pump(app, lambda: False, timeout=0.3)
    assert "c:/a.bin" in nxt.fs and "c:/b.bin" not in nxt.fs
    assert not (tmp_path / "readme.txt").exists()
    nxt.drop()


def test_dragging_next_entries_back_onto_the_next_pane_does_nothing(app, window):
    w, listener = window
    nxt = connect_next(app, w, listener)
    pane = w.next_pane()
    assert pump(app, lambda: "games" in pane.names())
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent

    pane.select(["readme.txt"])
    mime = pane.drag_mime()
    view = pane.list_view().viewport()
    point = pane.row_center("games")
    for kind in (QDragEnterEvent, QDragMoveEvent, QDropEvent):
        QApplication.sendEvent(view, kind(point, Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
    pump(app, lambda: False, timeout=0.3)
    assert not w.operation_running()
    assert pane.names() == ["games", "readme.txt"]
    assert sorted(nxt.fs) == sorted(k.lower() for k in FS)
    nxt.drop()


def test_next_entries_can_only_be_dragged_as_a_copy_so_no_row_is_removed(app, window):
    from PySide6.QtCore import Qt

    w, listener = window
    nxt = connect_next(app, w, listener)
    pane = w.next_pane()
    assert pump(app, lambda: "readme.txt" in pane.names())
    assert pane.list_view().supportedDragActions() == Qt.CopyAction  # a Move would remove the source rows
    nxt.drop()


def test_new_folder_creates_it_on_the_next_and_shows_it(app, window):
    w, listener = window
    nxt = connect_next(app, w, listener)
    pane = w.next_pane()
    assert pump(app, lambda: "games" in pane.names())
    w.prompts.name = "demos"
    w.new_folder()
    assert pump(app, lambda: "demos" in pane.names(), timeout=5)
    assert nxt.fs["c:/demos"] is None
    w.prompts.name = None  # cancelled prompt: nothing happens
    w.new_folder()
    assert not w.operation_running()
    nxt.drop()


def test_rename_changes_the_name_on_the_next_and_in_the_listing(app, window):
    w, listener = window
    nxt = connect_next(app, w, listener)
    pane = w.next_pane()
    assert pump(app, lambda: "readme.txt" in pane.names())
    pane.select(["readme.txt"])
    w.prompts.name = "intro.txt"
    w.rename_selected()
    assert w.prompts.asked[-1][1] == "readme.txt"  # the prompt starts from the current name
    assert pump(app, lambda: "intro.txt" in pane.names() and "readme.txt" not in pane.names(), timeout=5)
    assert nxt.fs["c:/intro.txt"] == b"hello"
    nxt.drop()


def test_rename_needs_exactly_one_selected_entry_and_a_plain_name(app, window):
    w, listener = window
    nxt = connect_next(app, w, listener)
    pane = w.next_pane()
    assert pump(app, lambda: "readme.txt" in pane.names())
    pane.select(["readme.txt", "games"])
    w.prompts.name = "x"
    w.rename_selected()
    assert not w.operation_running() and w.prompts.asked == []
    pane.select(["readme.txt"])
    w.prompts.name = "../evil"
    w.rename_selected()
    assert not w.operation_running()
    pump(app, lambda: False, timeout=0.2)
    assert "c:/readme.txt" in nxt.fs
    nxt.drop()


def test_delete_asks_naming_the_count_and_the_first_item_then_removes_everything(app, window):
    w, listener = window
    nxt = connect_next(app, w, listener)
    pane = w.next_pane()
    assert pump(app, lambda: "games" in pane.names())
    pane.select(["games", "readme.txt"])
    w.delete_selected()
    assert len(w.prompts.confirmations) == 1
    assert "2" in w.prompts.confirmations[0] and "games" in w.prompts.confirmations[0]
    assert pump(app, lambda: pane.names() == [], timeout=5)
    assert "c:/games" not in nxt.fs and "c:/games/manic.tap" not in nxt.fs
    assert "c:/readme.txt" not in nxt.fs
    nxt.drop()


def test_declining_the_delete_confirmation_deletes_nothing(app, window):
    w, listener = window
    nxt = connect_next(app, w, listener)
    pane = w.next_pane()
    assert pump(app, lambda: "games" in pane.names())
    pane.select(["games"])
    w.prompts.confirm = False
    w.delete_selected()
    assert not w.operation_running()
    pump(app, lambda: False, timeout=0.2)
    assert "c:/games/manic.tap" in nxt.fs and pane.names() == ["games", "readme.txt"]
    nxt.drop()


def test_next_buttons_name_the_next_and_follow_the_selection(app, window):
    w, listener = window
    assert not w.delete_enabled() and not w.rename_enabled()  # no Session yet
    nxt = connect_next(app, w, listener)
    pane = w.next_pane()
    assert pump(app, lambda: "games" in pane.names())
    assert all("Next" in t for t in (w.delete_text(), w.rename_text(), w.new_folder_text()))
    assert w.new_folder_enabled()
    assert not w.delete_enabled() and not w.rename_enabled()  # nothing selected
    pane.select(["readme.txt"])
    assert w.delete_enabled() and w.rename_enabled()
    pane.select(["readme.txt", "games"])
    assert w.delete_enabled() and not w.rename_enabled()  # rename takes exactly one
    pane.select([])
    assert not w.delete_enabled()
    nxt.drop()


def test_the_delete_confirmation_says_it_deletes_on_the_next(app, window):
    w, listener = window
    nxt = connect_next(app, w, listener)
    pane = w.next_pane()
    assert pump(app, lambda: "readme.txt" in pane.names())
    pane.select(["readme.txt"])
    w.prompts.confirm = False
    w.delete_selected()
    assert "Next" in w.prompts.confirmations[0]
    nxt.drop()


def test_disconnect_ends_the_session_and_leaves_the_window_waiting_for_another_next(app, window):
    w, listener = window
    assert not w.disconnect_enabled()
    nxt = connect_next(app, w, listener)
    assert pump(app, w.disconnect_enabled)
    w._disconnect.click()
    assert nxt.ended.wait(timeout=5)  # told to quit, not left polling
    assert pump(app, lambda: w.next_pane_state() == "waiting", timeout=5)
    assert w.isVisible() and not w.disconnect_enabled()
    second = FakeNext(listener.port, fs=FS, free_blocks={"C": 2048})
    end = time.time() + 3
    while second.connect() != b"Listening" and time.time() < end:
        second = FakeNext(listener.port, fs=FS, free_blocks={"C": 2048})
        time.sleep(0.02)
    assert pump(app, lambda: w.next_pane_state() == "connected")
    second.drop()

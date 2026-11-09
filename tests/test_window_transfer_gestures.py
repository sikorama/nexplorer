"""Transfer gestures: double-click, Enter, F5, the centre buttons, Send/Receive menu entries and the
cross-pane clipboard, against the fake Next."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from nexplorer.protocol import Listener
from nexplorer.ui.main_window import MainWindow
from tests.conftest import dispose, pump
from tests.fake_next import FakeNext

FS = {"c:/dest": None, "c:/dest/sub": None, "c:/dest/sub/in.txt": b"inside", "c:/dest/n.txt": b"from-next"}


@pytest.fixture
def setup(app, tmp_path):
    listener = Listener(host="127.0.0.1", port=0)
    listener.start()
    made = []

    def build(connect=True):
        (tmp_path / "l.txt").write_bytes(b"from-local")
        (tmp_path / "folder").mkdir(exist_ok=True)
        w = MainWindow(listener, local_addresses=lambda: [], confirm_overwrite=lambda p, r: ("overwrite", False))
        made.append(w)
        w.show()
        w.local_pane().go_to(str(tmp_path))
        assert pump(app, lambda: "l.txt" in w.local_pane().names())
        nxt = None
        if connect:
            nxt = FakeNext(listener.port, fs=dict(FS), free_blocks={"C": 2048})
            nxt.connect()
            assert pump(app, lambda: w.next_pane_state() == "connected")
            assert pump(app, lambda: w.next_pane().path() == "c:/" and "dest" in w.next_pane().names())
            w.next_pane().enter("dest")
            assert pump(app, lambda: w.next_pane().path() == "c:/dest" and "n.txt" in w.next_pane().names())
        return w, nxt

    yield build, tmp_path
    for w in made:
        w.close()
        dispose(app, w)
    listener.stop()


def double_click(pane, name):
    view, pos = pane.list_view().viewport(), pane.row_center(name)
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, pos)
    QTest.mouseDClick(view, Qt.LeftButton, Qt.NoModifier, pos)


def idle(app, w):
    assert pump(app, lambda: not w.operation_running(), timeout=10)


def test_double_click_a_local_file_sends_it_and_a_next_file_is_received(app, setup):
    build, tmp = setup
    w, nxt = build()
    double_click(w.local_pane(), "l.txt")
    assert pump(app, lambda: nxt.fs.get("c:/dest/l.txt") == b"from-local", timeout=10)
    idle(app, w)
    double_click(w.next_pane(), "n.txt")
    assert pump(app, lambda: (tmp / "n.txt").exists() and (tmp / "n.txt").read_bytes() == b"from-next", timeout=10)
    nxt.drop()


def test_double_click_a_folder_enters_it_without_transfer(app, setup):
    build, tmp = setup
    w, nxt = build()
    double_click(w.local_pane(), "folder")
    assert pump(app, lambda: w.local_pane().path() == str(tmp / "folder"))
    double_click(w.next_pane(), "sub")
    assert pump(app, lambda: w.next_pane().path() == "c:/dest/sub")
    assert not w.operation_running() and "c:/dest/folder" not in nxt.fs
    nxt.drop()


def test_enter_enters_a_folder_and_transfers_nothing_on_a_file(app, setup):
    build, tmp = setup
    w, nxt = build()
    tree = w.local_pane().list_view()
    w.local_pane().select(["l.txt"])
    tree.setCurrentItem(tree.selectedItems()[0])
    QTest.keyClick(tree, Qt.Key_Return)
    pump(app, lambda: False, timeout=0.3)
    assert not w.operation_running() and "c:/dest/l.txt" not in nxt.fs
    w.local_pane().select(["folder"])
    tree.setCurrentItem(tree.selectedItems()[0])
    QTest.keyClick(tree, Qt.Key_Return)
    assert pump(app, lambda: w.local_pane().path() == str(tmp / "folder"))
    nxt.drop()


def test_double_click_a_file_without_a_session_does_nothing(app, setup):
    build, tmp = setup
    w, _ = build(connect=False)
    double_click(w.local_pane(), "l.txt")
    pump(app, lambda: False, timeout=0.3)
    assert not w.operation_running()


def test_f5_transfers_the_selection_of_the_active_pane_both_ways(app, setup):
    build, tmp = setup
    w, nxt = build()
    w.activate_pane("local")
    w.local_pane().select(["l.txt", "folder"])
    QTest.keyClick(w.local_pane().list_view(), Qt.Key_F5)
    assert pump(app, lambda: nxt.fs.get("c:/dest/l.txt") == b"from-local", timeout=10)
    idle(app, w)
    w.activate_pane("next")
    w.next_pane().select(["n.txt", "sub"])
    QTest.keyClick(w.next_pane().list_view(), Qt.Key_F5)
    assert pump(app, lambda: (tmp / "n.txt").exists() and (tmp / "sub" / "in.txt").exists(), timeout=10)
    nxt.drop()


def test_f5_without_a_session_does_nothing(app, setup):
    build, _ = setup
    w, _ = build(connect=False)
    w.local_pane().select(["l.txt"])
    QTest.keyClick(w.local_pane().list_view(), Qt.Key_F5)
    pump(app, lambda: False, timeout=0.3)
    assert not w.operation_running()


def test_centre_buttons_and_menu_entries_fix_their_direction_whichever_pane_is_active(app, setup):
    build, tmp = setup
    w, nxt = build()
    assert not w.centre_button_enabled("send") and not w.centre_button_enabled("receive")
    w.activate_pane("next")  # the Local selection still drives Send
    w.local_pane().select(["l.txt"])
    assert w.centre_button_enabled("send") and w.entry_enabled("Transfer", "Send")
    w.click_centre_button("send")
    assert pump(app, lambda: nxt.fs.get("c:/dest/l.txt") == b"from-local", timeout=10)
    idle(app, w)
    w.activate_pane("local")
    w.local_pane().select([])
    w.next_pane().select(["n.txt"])
    assert w.centre_button_enabled("receive") and w.entry_enabled("Transfer", "Receive")
    w.trigger_menu("Transfer", "Receive")
    assert pump(app, lambda: (tmp / "n.txt").exists(), timeout=10)
    nxt.drop()


def test_copy_then_paste_across_panes_transfers_in_both_directions(app, setup):
    build, tmp = setup
    w, nxt = build()
    w.activate_pane("local")
    w.local_pane().select(["l.txt"])
    w.trigger_menu("Edit", "Copy")
    w.activate_pane("next")
    assert w.entry_enabled("Edit", "Paste")
    w.trigger_menu("Edit", "Paste")
    assert pump(app, lambda: nxt.fs.get("c:/dest/l.txt") == b"from-local", timeout=10)
    idle(app, w)
    w.next_pane().select(["n.txt"])
    w.trigger_menu("Edit", "Copy")
    w.activate_pane("local")
    assert w.entry_enabled("Edit", "Paste")
    w.trigger_menu("Edit", "Paste")
    assert pump(app, lambda: (tmp / "n.txt").exists(), timeout=10)
    nxt.drop()


def test_cross_pane_cut_leaves_paste_greyed_but_same_side_cut_works(app, setup):
    build, tmp = setup
    w, nxt = build()
    w.activate_pane("local")
    w.local_pane().select(["l.txt"])
    w.trigger_menu("Edit", "Cut")
    w.activate_pane("next")
    assert not w.entry_enabled("Edit", "Paste")
    w.activate_pane("local")
    w.local_pane().enter("folder")
    assert pump(app, lambda: w.local_pane().path() == str(tmp / "folder"))
    assert w.entry_enabled("Edit", "Paste")
    w.trigger_menu("Edit", "Paste")
    assert pump(app, lambda: (tmp / "folder" / "l.txt").exists() and not (tmp / "l.txt").exists())
    idle(app, w)
    assert not w.entry_enabled("Edit", "Paste")
    w.activate_pane("next")
    w.next_pane().select(["n.txt"])
    w.trigger_menu("Edit", "Cut")
    w.activate_pane("local")
    assert not w.entry_enabled("Edit", "Paste")
    nxt.drop()

"""Icons, toolbar and list styling seen through the window."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nexplorer.ui import icons
from tests.conftest import pump
from tests.test_window_actions import connected, focus, window  # noqa: F401


def test_the_toolbar_holds_the_frequent_shared_actions(app, window):
    w, _ = window
    assert w.toolbar_action_keys() == list(icons.TOOLBAR_ACTIONS)
    assert all(has_icon for _, _, has_icon in w.toolbar_entries())


def test_the_toolbar_follows_the_menu_enablement(app, window):
    w, listener = window
    nxt = connected(app, w, listener)
    w.next_pane().select(["readme.txt"])
    focus(app, w, "next")
    menus = {t: dict((label, en) for label, _, en in w.menu_entries(t)) for t in ("File", "Edit", "Transfer", "View")}
    flat = {k: v for m in menus.values() for k, v in m.items()}
    for label, enabled, _ in w.toolbar_entries():
        assert flat[label] == enabled
    focus(app, w, "local")
    flat = {k: v for t in menus for k, v in dict((l, e) for l, _, e in w.menu_entries(t)).items()}
    for label, enabled, _ in w.toolbar_entries():
        assert flat[label] == enabled
    nxt.drop()


def test_menu_entries_have_icons(app, window):
    w, _ = window
    for menu, label in (("File", "New folder"), ("File", "Quit"), ("Edit", "Copy"), ("Transfer", "Send"), ("Help", "About")):
        assert w.menu_entry_has_icon(menu, label)


def test_both_lists_alternate_row_colours(app, window):
    w, _ = window
    assert w.local_pane().list_view().alternatingRowColors()
    assert w.next_pane().list_view().alternatingRowColors()


def _pixels(icon):
    return icon.pixmap(16, 16).toImage()


def test_local_rows_use_the_system_icons(app, window):
    w, _ = window
    assert pump(app, lambda: "local.txt" in w.local_pane().names())
    view = w.local_pane().list_view()
    item = next(view.topLevelItem(i) for i in range(view.topLevelItemCount()) if view.topLevelItem(i).text(0) == "local.txt")
    assert not item.icon(0).isNull()


def test_next_rows_have_distinct_icons_by_type(app, window):
    w, listener = window
    nxt = connected(app, w, listener)
    pane = w.next_pane()
    pane._entries = [
        *pane._entries,
        *(type(pane._entries[0])(n, False, 1) for n in ("a.nex", "a.tap", "a.sna", "a.bas")),
    ]
    pane._fill()
    view = pane.list_view()
    images = {}
    for i in range(view.topLevelItemCount()):
        item = view.topLevelItem(i)
        images[item.text(0)] = _pixels(item.icon(0))
    folders = [i for n, i in images.items() if n in {r[0] for r in pane.rows() if r[2] == "Folder"}]
    assert folders, images.keys()
    kinds = [images[n] for n in ("a.nex", "a.tap", "a.sna", "a.bas", "readme.txt")] + [folders[0]]
    for i, a in enumerate(kinds):
        for b in kinds[i + 1:]:
            assert a != b
    nxt.drop()


def test_icons_can_be_retinted(app, window):
    w, _ = window
    before = _pixels(w._actions.action("copy").icon())
    w.set_icon_colour("#ff0000")
    assert _pixels(w._actions.action("copy").icon()) != before

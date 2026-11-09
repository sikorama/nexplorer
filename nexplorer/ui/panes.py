"""The two file panes: a shared folder view and its Local and Next backends."""
from __future__ import annotations

import os
import shutil
import threading
from typing import Callable, Protocol

from PySide6.QtCore import QEvent, QMimeData, QObject, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nexplorer.i18n import tr
from nexplorer.listing import sort_entries
from nexplorer.local_roots import Root, local_roots
from nexplorer.protocol import Entry, RemoteError, Session


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    value = float(size)
    for unit in ("KB", "MB", "GB"):
        value /= 1024
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
    raise AssertionError


def type_label(entry: Entry) -> str:
    if entry.is_dir:
        return tr("Folder")
    name = entry.name.strip(".")
    return name.rpartition(".")[2].upper() if "." in name else tr("File")


class Backend(Protocol):
    def list(self, path: str) -> list[Entry]: ...
    def join(self, path: str, name: str) -> str: ...
    def parent(self, path: str) -> str: ...


class LocalBackend:
    def join(self, path: str, name: str) -> str:
        return os.path.join(path, name)

    def parent(self, path: str) -> str:
        return os.path.dirname(path.rstrip(os.sep)) or path

    def list(self, path: str) -> list[Entry]:
        entries = []
        with os.scandir(path) as it:
            for item in it:
                try:
                    is_dir = item.is_dir()
                    size = 0 if is_dir else item.stat().st_size
                except OSError:
                    continue
                entries.append(Entry(item.name, is_dir, size))
        return entries


NEXT_ENTRIES_MIME = "application/x-nexplorer-next-entries"
LOCAL_ENTRIES_MIME = "application/x-nexplorer-local-entries"


class _Tree(QTreeWidget):
    """The list of entries; accepts files dropped from outside when `accept_urls` is set."""

    urls_dropped = Signal(list, str)  # local paths, name of the folder row under the cursor ("" if none)
    next_entries_dropped = Signal(list, str)  # names dragged out of the Next pane, folder row hit ("" if none)
    local_entries_dropped = Signal(list, str, bool)  # names dragged inside the Local pane, folder row hit, copy?

    def __init__(self):
        super().__init__()
        self.accept_urls = False
        self.accept_next_entries = False
        self.folder_rows_only = False  # Next entries are only taken when dropped on a folder row
        self.accept_local_entries = False  # Local entries are only taken when dropped on a folder row
        self.drag_format = NEXT_ENTRIES_MIME  # what a drag of this pane's rows carries

    def _folder_row(self, event) -> str:
        item = self.itemAt(event.position().toPoint())
        return item.text(0) if item is not None and item.data(0, Qt.UserRole) else ""

    def mimeData(self, items) -> QMimeData:
        mime = QMimeData()
        mime.setData(self.drag_format, "\n".join(i.text(0) for i in items).encode())
        return mime

    def _carries_wanted(self, event) -> bool:
        mime = event.mimeData()
        return (
            (self.accept_urls and mime.hasUrls())
            or (self.accept_next_entries and mime.hasFormat(NEXT_ENTRIES_MIME))
            or (self.accept_local_entries and mime.hasFormat(LOCAL_ENTRIES_MIME))
        )

    def _wanted(self, event) -> bool:
        mime = event.mimeData()
        if self.accept_urls and mime.hasUrls():
            return True
        if self.accept_next_entries and mime.hasFormat(NEXT_ENTRIES_MIME):
            return not self.folder_rows_only or bool(self._folder_row(event))
        if self.accept_local_entries and mime.hasFormat(LOCAL_ENTRIES_MIME):
            return bool(self._folder_row(event))
        return False

    def dragEnterEvent(self, event) -> None:
        # Accepted wherever it lands: on X11 an ignored enter stops the moves, so the drag could
        # not become valid until it left and came back. dragMoveEvent decides row by row.
        if self._carries_wanted(event):
            event.acceptProposedAction()
        else:
            event.ignore()  # never the default internal move: rows are not reordered by hand

    def dragMoveEvent(self, event) -> None:
        if self._wanted(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        if not self._wanted(event):
            event.ignore()
            return
        if event.mimeData().hasFormat(LOCAL_ENTRIES_MIME):
            names = bytes(event.mimeData().data(LOCAL_ENTRIES_MIME)).decode().split("\n")
            copy = bool(event.modifiers() & Qt.ShiftModifier)
            event.acceptProposedAction()
            self.local_entries_dropped.emit([n for n in names if n], self._folder_row(event), copy)
            return
        if event.mimeData().hasFormat(NEXT_ENTRIES_MIME):
            names = bytes(event.mimeData().data(NEXT_ENTRIES_MIME)).decode().split("\n")
            event.acceptProposedAction()
            self.next_entries_dropped.emit([n for n in names if n], self._folder_row(event))
            return
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        item = self.itemAt(event.position().toPoint())
        event.acceptProposedAction()
        self.urls_dropped.emit(paths, item.text(0) if item else "")


class _Loaded(QObject):
    done = Signal(int, str, object, str)  # request id, path, entries, error


class _DriveCombo(QComboBox):
    """The drive selector; tells its pane before the list drops down, so the choices can be re-read."""

    opening = Signal()

    def showPopup(self) -> None:
        self.opening.emit()
        super().showPopup()


class FolderPane(QWidget):
    """One side: header, drive selector with free space, Up and address, list, status line.
    Both sides share this layout so their rows line up."""

    focused = Signal()  # the pane or one of its controls got the keyboard focus
    context_requested = Signal(str, object)  # row name ("" on empty space), global position

    def __init__(self, backend: Backend, path: str, title: str = ""):
        super().__init__()
        self._backend = backend
        self._loaded = _Loaded()
        self._loaded.done.connect(self._on_loaded)
        self._request = 0
        self._loading = False
        self._path = path
        self._entries: list[Entry] = []
        self._sort = ("name", False)
        self._show_hidden = False
        self._error = ""
        self._closed = False

        self._tree = _Tree()
        self._tree.setRootIsDecorated(False)
        self._tree.setHeaderLabels([tr("Name"), tr("Size"), tr("Type")])
        self._tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree.header().setSectionsClickable(True)
        self._tree.header().sectionClicked.connect(
            lambda column: self.sort_by(("name", "size", "type")[column])
        )
        self._up = QPushButton(tr("Up"))
        self._up.clicked.connect(self.go_up)
        self._address = QLineEdit(path)
        self._address.returnPressed.connect(lambda: self.go_to(self._address.text()))
        self._status = QLabel()
        self._title = QLabel(title)
        self._title.setStyleSheet("font-weight: bold")
        self._drives = _DriveCombo()
        self._drives.opening.connect(self.open_drive_selector)
        self._drives.activated.connect(lambda _i: self.switch_drive(self._drives.currentText()))
        self._free = QLabel()
        self._stack = QStackedWidget()
        self._stack.addWidget(self._tree)
        self.selection_changed = self._tree.itemSelectionChanged
        self._tree.itemActivated.connect(lambda item, _c: self.enter(item.text(0)))
        col = QVBoxLayout(self)
        col.addWidget(self._title)
        drive_bar = QHBoxLayout()
        drive_bar.addWidget(QLabel(tr("Drive")))
        drive_bar.addWidget(self._drives)
        drive_bar.addWidget(self._free, 1)
        col.addLayout(drive_bar)
        bar = QHBoxLayout()
        bar.addWidget(self._up)
        bar.addWidget(self._address, 1)
        col.addLayout(bar)
        col.addWidget(self._stack, 1)
        col.addWidget(self._status)
        self._controls = (self._drives, self._up, self._address)
        for widget in (self._tree, *self._controls):
            widget.installEventFilter(self)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._active = False
        self.set_active(False)
        if path:
            self.load(path)

    # -- active pane
    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.FocusIn:
            self.focused.emit()
        return False

    def set_active(self, active: bool) -> None:
        """Mark the pane as the one the actions apply to: an accent border on its header and list."""
        self._active = active
        colour = "palette(highlight)" if active else "transparent"
        self._title.setStyleSheet(f"font-weight: bold; border-bottom: 2px solid {colour}")
        self._tree.setStyleSheet(f"QTreeWidget {{ border: 2px solid {colour}; }}")

    def is_active(self) -> bool:
        return self._active

    def select_all(self) -> None:
        self._tree.selectAll()

    def prepare_context(self, row: str) -> None:
        """A right-click on `row` ("" for empty space): an unselected row is selected alone,
        empty space clears the selection, a selected row keeps the whole selection."""
        if not row:
            self._tree.clearSelection()
        elif row not in self.selected_names():
            self.select([row])

    def _on_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        self.context_requested.emit(item.text(0) if item is not None else "", self._tree.viewport().mapToGlobal(pos))

    # -- drives
    def open_drive_selector(self) -> None:
        """The drive choices are about to be shown (a subclass re-reads them)."""

    def switch_drive(self, label: str) -> None:
        """Show the drive the selector calls `label` (a subclass knows what that means)."""

    def drives(self) -> list[str]:
        return [self._drives.itemText(i) for i in range(self._drives.count())]

    def free_space_text(self) -> str:
        return self._free.text()

    def set_controls_enabled(self, enabled: bool) -> None:
        """Grey or enable the drive selector, Up and the address field; they stay visible."""
        for widget in self._controls:
            widget.setEnabled(enabled)

    def controls_enabled(self) -> bool:
        return self._address.isEnabled()

    def controls_visible(self) -> bool:
        return self._address.isVisibleTo(self) and self._up.isVisibleTo(self) and self._drives.isVisibleTo(self)

    # -- navigation
    def go_to(self, path: str) -> None:
        self.load(path)

    def reload(self) -> None:
        if self._path:
            self.load(self._path)

    def folder_path(self, name: str = "") -> str:
        """The folder shown, or its subfolder `name` (the shown folder if `name` is not a folder)."""
        if name and any(e.name == name and e.is_dir for e in self._entries):
            return self._backend.join(self._path, name)
        return self._path

    def go_up(self) -> None:
        self.load(self._backend.parent(self._path))

    def enter(self, name: str) -> None:
        if any(e.name == name and e.is_dir for e in self._entries):
            self.load(self._backend.join(self._path, name))

    # -- loading, off the UI thread
    def load(self, path: str) -> None:
        self._request += 1
        self._loading = True
        request = self._request

        def work() -> None:
            try:
                entries, error = self._backend.list(path), ""
            except Exception as exc:  # noqa: BLE001 - shown to the user
                entries, error = [], str(exc) or exc.__class__.__name__
            if not self._closed:
                try:
                    self._loaded.done.emit(request, path, entries, error)
                except RuntimeError:  # pane already gone
                    pass

        threading.Thread(target=work, daemon=True).start()

    def shutdown(self) -> None:
        """Stop reacting to listings still in flight (the window is closing)."""
        self._closed = True

    def sort_by(self, key: str) -> None:
        """Sort by name, size or type; asking again for the same key reverses it."""
        descending = self._sort == (key, False)
        self._sort = (key, descending)
        self._fill()

    def sort(self) -> tuple[str, bool]:
        return self._sort

    def set_sort(self, sort: tuple[str, bool]) -> None:
        self._sort = sort
        self._fill()

    def set_show_hidden(self, show: bool) -> None:
        self._show_hidden = show
        self._fill()

    def select(self, names: list[str]) -> None:
        self._tree.clearSelection()
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item.text(0) in names:
                item.setSelected(True)

    def selected_names(self) -> list[str]:
        return [
            self._tree.topLevelItem(i).text(0)
            for i in range(self._tree.topLevelItemCount())
            if self._tree.topLevelItem(i).isSelected()
        ]

    def entries(self) -> list[Entry]:
        return list(self._entries)

    def selected_entries(self) -> list[Entry]:
        names = set(self.selected_names())
        return [e for e in self._entries if e.name in names]

    def _on_loaded(self, request: int, path: str, entries: list, error: str) -> None:
        if request != self._request:
            return
        self._loading = False
        self._error = error
        self._status.setText(error)
        if error:
            self._address.setText(self._path)
            return
        self._path = path
        self._address.setText(path)
        self._entries = entries
        self._fill()

    def _fill(self) -> None:
        self._tree.clear()
        by, descending = self._sort
        for e in sort_entries(self._entries, by, descending):
            if e.name.startswith(".") and not self._show_hidden and e.name not in (".", ".."):
                continue
            row = QTreeWidgetItem([e.name, "" if e.is_dir else format_size(e.size), type_label(e)])
            row.setData(0, Qt.UserRole, e.is_dir)
            self._tree.addTopLevelItem(row)

    def drag_mime(self) -> QMimeData:
        """What a drag of the selected rows carries (also used by tests)."""
        return self._tree.mimeData(self._tree.selectedItems())

    # -- observation points for tests
    def address_field(self) -> QLineEdit:
        return self._address

    def list_view(self) -> QTreeWidget:
        return self._tree

    def row_center(self, name: str):
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item.text(0) == name:
                return self._tree.visualItemRect(item).center()
        raise KeyError(name)

    def path(self) -> str:
        return self._path

    def error(self) -> str:
        return self._error

    def is_loading(self) -> bool:
        return self._loading

    def names(self) -> list[str]:
        return [r[0] for r in self.rows()]

    def rows(self) -> list[tuple[str, str, str]]:
        out = []
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            out.append(tuple(item.text(c) for c in range(3)))
        return out


class LocalPane(FolderPane):
    def __init__(self, path: str, roots: Callable[[], list[Root]] = local_roots):
        self._roots_source = roots
        self._roots: list[Root] = []
        super().__init__(LocalBackend(), path, tr("Local"))
        self._tree.accept_next_entries = True
        self._tree.setAcceptDrops(True)
        self.next_entries_dropped = self._tree.next_entries_dropped
        self._tree.accept_local_entries = True  # dragging inside this pane moves (Shift: copies)
        self._tree.drag_format = LOCAL_ENTRIES_MIME
        self._tree.setDragEnabled(True)
        self._tree.setSupportedDragActions(Qt.CopyAction)  # a Move would remove the source rows
        self._tree.setDragDropMode(QAbstractItemView.DragDrop)
        self.local_entries_dropped = self._tree.local_entries_dropped
        self.open_drive_selector()

    def open_drive_selector(self) -> None:
        """Read the roots again (a card may have been plugged in) and mark the one holding the folder."""
        try:
            self._roots = list(self._roots_source())
        except OSError:
            self._roots = []
        self._drives.clear()
        self._drives.addItems([label for label, _ in self._roots])
        self._mark_current_root()

    def _mark_current_root(self) -> None:
        here = os.path.normcase(self._path)
        best = max(
            (r for r in self._roots if here.startswith(os.path.normcase(r[1]))),
            key=lambda r: len(r[1]),
            default=None,
        )
        if best is not None:
            self._drives.setCurrentText(best[0])

    def switch_drive(self, label: str) -> None:
        for name, path in self._roots:
            if name == label:
                self.load(path)
                return

    def _on_loaded(self, request: int, path: str, entries: list, error: str) -> None:
        super()._on_loaded(request, path, entries, error)
        if request != self._request or error:
            return
        self._mark_current_root()
        try:
            self._free.setText(f"{format_size(shutil.disk_usage(path).free)} {tr('free')}")
        except OSError:
            self._free.setText("")


class NextBackend:
    """Lists folders of the Next through the current Session (set while connected)."""

    def __init__(self):
        self.session: Session | None = None
        self.allowed_drives: set[str] = set()  # upper-case letters reported by `W`

    def list(self, path: str) -> list[Entry]:
        session = self.session
        if session is None:
            raise ConnectionError(tr("No ZX Spectrum Next connected"))
        # Any path on an unmounted or floppy drive crashes the dot: only the
        # drives the Next reported are ever sent (docs/protocol.md, `W`).
        if len(path) < 2 or path[1] != ":" or path[0].upper() not in self.allowed_drives:
            raise PermissionError(tr("Drive not available on the ZX Spectrum Next"))
        return session.list_dir(path, timeout=60)

    def join(self, path: str, name: str) -> str:
        if name == "..":
            return self.parent(path)
        if name == ".":
            return path
        return path.rstrip("/") + "/" + name

    def parent(self, path: str) -> str:
        drive, _, rest = path.partition(":")
        parts = [p for p in rest.split("/") if p]
        return f"{drive}:/" + "/".join(parts[:-1])


class _Info(QObject):
    done = Signal(object, object, str)  # session, Drives or None, free-space text


class NextPane(FolderPane):
    """The Next's folders, with a drive switch and the free space of the drive."""

    def __init__(self):
        self._next = NextBackend()
        super().__init__(self._next, "", tr("ZX Spectrum Next"))
        self._tree.accept_urls = True
        self._tree.setAcceptDrops(True)
        self._tree.accept_next_entries = True
        self._tree.folder_rows_only = True
        self.entries_moved = self._tree.next_entries_dropped
        self._tree.setDragEnabled(True)
        self._tree.setSupportedDragActions(Qt.CopyAction)  # a Move would remove the source rows
        self._tree.setDragDropMode(QAbstractItemView.DragDrop)
        self.files_dropped = self._tree.urls_dropped
        self._info = _Info()
        self._info.done.connect(self._on_info)
        self._drive = ""
        self.preferred_path = ""  # folder to reopen on the next Session, if its drive is there
        self._fallback = ""  # drive root to show if the preferred folder cannot be listed

    def bind(self, session: Session) -> None:
        """A Session opened: show the root of the Next's current drive."""
        self.unbind()
        self._next.session = session

        def work() -> None:
            try:
                drives = session.drives(timeout=30)
            except (ConnectionError, TimeoutError, RemoteError):
                drives = None
            free = self._measure(session, self._start_drive(drives) if drives else "")
            self._emit_info(session, drives, free)

        threading.Thread(target=work, daemon=True).start()

    def _start_drive(self, drives) -> str:
        """The drive to open: the one of the preferred folder if the Next has it, else the current one."""
        wanted = self.preferred_path[:1].upper()
        return wanted if self.preferred_path[1:2] == ":" and wanted in [d.upper() for d in drives.letters] else drives.current

    def unbind(self) -> None:
        """The Session ended: forget everything about it (the folder shown is kept for the next one)."""
        self.preferred_path = self._path or self.preferred_path
        self._fallback = ""
        self._next.session = None
        self._next.allowed_drives = set()
        self._request += 1
        self._loading = False
        self._entries = []
        self._path = ""
        self._drive = ""
        self._tree.clear()
        self._drives.clear()
        self._free.setText("")
        self._address.setText("")

    def switch_drive(self, letter: str) -> None:
        session = self._next.session
        if session is None:
            return
        self._drive = letter
        self._drives.setCurrentText(letter)
        self.load(f"{letter.lower()}:/")
        self._free.setText("")

        def work() -> None:
            self._emit_info(session, None, self._measure(session, letter))

        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def _measure(session: Session, drive: str) -> str:
        if not drive:
            return ""
        try:
            free = session.free_space(drive, timeout=30)
        except (ConnectionError, TimeoutError, RemoteError):
            return ""
        return "" if free is None else f"{format_size(free)} {tr('free')}"

    def _emit_info(self, session: Session, drives, free: str) -> None:
        if self._closed:
            return
        try:
            self._info.done.emit(session, drives, free)
        except RuntimeError:  # pane already gone
            pass

    def _on_info(self, session: Session, drives, free: str) -> None:
        if session is not self._next.session:
            return
        if drives is not None:
            self._next.allowed_drives = {letter.upper() for letter in drives.letters}
            self._drives.clear()
            self._drives.addItems(drives.letters)
            self._drive = self._start_drive(drives)
            root = f"{self._drive.lower()}:/"
            start = self.preferred_path if self.preferred_path[:1].upper() == self._drive else root
            self._fallback = root if start != root else ""
            self._drives.setCurrentText(self._drive)
            self.load(start)
        elif self._drive and self._drives.currentText() != self._drive:
            return
        self._free.setText(free)

    def _on_loaded(self, request: int, path: str, entries: list, error: str) -> None:
        if error and self._fallback and request == self._request:
            root, self._fallback = self._fallback, ""
            self.load(root)  # the remembered folder is gone: show the drive root instead
            return
        if request == self._request:
            self._fallback = ""
        super()._on_loaded(request, path, entries, error)

    def session(self) -> Session | None:
        return self._next.session

    def show_card(self, card: QWidget) -> None:
        """Show `card` in place of the list (nothing to browse yet)."""
        if self._stack.indexOf(card) < 0:
            self._stack.addWidget(card)
        self._stack.setCurrentWidget(card)

    def show_list(self) -> None:
        self._stack.setCurrentWidget(self._tree)

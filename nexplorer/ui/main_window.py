from __future__ import annotations

import base64
import os
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtNetwork import QAbstractSocket, QNetworkInterface
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QFrame,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from nexplorer import local_ops, overwrite
from nexplorer import settings as settings_store
from nexplorer.capabilities import MINIMUM_DOT, Capabilities, capabilities
from nexplorer.i18n import available_languages, set_language, tr
from nexplorer.compare import (
    Row,
    apply as apply_rows,
    compare_level,
    read_ignore,
    expand as expand_row,
    scan_all,
    recompare,
    verify as verify_rows,
)
from nexplorer.local_ops import Trash, system_trash
from nexplorer.local_roots import Root, local_roots
from nexplorer.protocol import Listener, RemoteError
from nexplorer.transfer import Result, copy, is_plain_name, make_folder, move, receive, remove, rename, send
from nexplorer.settings import THEMES, Settings
from nexplorer.ui.actions import LOCAL, NEXT, Binding, SharedActions
from nexplorer.ui.bridge import ListenerBridge
from nexplorer.ui import icons, theme
from nexplorer.ui.compare_view import CompareView
from nexplorer.ui.panes import LocalPane, NextPane, format_size

SYNC_COMMAND = ".sync5 -l"
CONFIG_FILE = "c:/sys/config/nextsync.cfg"


def local_ipv4_addresses() -> list[tuple[str, str]]:
    """(interface name, IPv4 address) for each usable network interface."""
    found = []
    for iface in QNetworkInterface.allInterfaces():
        flags = iface.flags()
        if not (flags & QNetworkInterface.IsUp) or flags & QNetworkInterface.IsLoopBack:
            continue
        for entry in iface.addressEntries():
            addr = entry.ip()
            if addr.protocol() == QAbstractSocket.IPv4Protocol:
                found.append((iface.humanReadableName(), addr.toString()))
    return found


def _one_row(row):
    """The row as if it were checked: a single transfer ignores the checkbox. A folder row
    goes alone, without the rows below it."""
    return replace(row, checked=True, children=None)


def _ask_name_dialog(title: str, initial: str = "") -> str | None:
    text, accepted = QInputDialog.getText(None, title, tr("Name"), text=initial)
    return text if accepted else None


def _confirm_delete_dialog(message: str) -> bool:
    answer = QMessageBox.warning(
        None, tr("Delete"), message, QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel
    )
    return answer == QMessageBox.Yes


def _confirm_permanent_dialog(message: str) -> bool:
    """The trash failed: delete for good or Cancel (the default)."""
    box = QMessageBox(QMessageBox.Warning, tr("Delete"), message)
    delete_button = box.addButton(tr("Delete permanently"), QMessageBox.DestructiveRole)
    cancel_button = box.addButton(tr("Cancel"), QMessageBox.RejectRole)
    box.setDefaultButton(cancel_button)
    box.setEscapeButton(cancel_button)
    box.exec()
    return box.clickedButton() is delete_button


def _confirm_overwrite_dialog(path: str, remaining: int) -> tuple[str, bool]:
    """Overwrite, Skip or Cancel for one name that already exists; Cancel is the default."""
    box = QMessageBox(QMessageBox.Warning, tr("Already exists"), f"{path}\n\n{tr('already exists. Overwrite it?')}")
    overwrite_button = box.addButton(tr("Overwrite"), QMessageBox.AcceptRole)
    skip_button = box.addButton(tr("Skip"), QMessageBox.RejectRole)
    cancel_button = box.addButton(tr("Cancel"), QMessageBox.RejectRole)
    box.setDefaultButton(cancel_button)
    box.setEscapeButton(cancel_button)
    everyone = QCheckBox(f"{tr('Apply to all')} ({remaining})")
    if remaining > 1:
        box.setCheckBox(everyone)
    box.exec()
    clicked = box.clickedButton()
    answer = (
        overwrite.OVERWRITE
        if clicked is overwrite_button
        else overwrite.SKIP
        if clicked is skip_button
        else overwrite.CANCEL
    )
    return answer, everyone.isChecked()


def _about_dialog() -> None:
    QMessageBox.about(
        None,
        tr("About"),
        "nexplorer\n\n" + tr("A file manager for the SD card of a ZX Spectrum Next, driven over Wi-Fi."),
    )


# Shared actions that target a pane: greyed while the Compare view replaces the panes.
COMPARE_GREYED = (
    "new_folder", "rename", "delete", "copy", "cut", "paste", "select_all",
    "send", "receive", "transfer", "refresh",
)  # fmt: skip


def _theme_label(code: str) -> str:
    return {"light": tr("Light"), "dark": tr("Dark"), "system": tr("System")}[code]


def _settings_dialog(current: Settings) -> Settings | None:
    dialog = QDialog()
    dialog.setWindowTitle(tr("Settings"))
    hidden = QCheckBox(tr("Show hidden files"))
    hidden.setChecked(current.show_hidden)
    crc = QCheckBox(tr("Verify the CRC after each upload"))
    crc.setChecked(current.crc_after_upload)
    language = QComboBox()
    language.addItems(available_languages())
    language.setCurrentText(current.language)
    theme_box = QComboBox()
    for code in THEMES:
        theme_box.addItem(_theme_label(code), code)
    theme_box.setCurrentIndex(THEMES.index(current.theme))
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    form = QFormLayout(dialog)
    form.addRow(hidden)
    form.addRow(crc)
    form.addRow(tr("Language"), language)
    form.addRow(tr("Theme"), theme_box)
    form.addRow(buttons)
    if dialog.exec() != QDialog.Accepted:
        return None
    return Settings(
        **{
            **current.__dict__,
            "show_hidden": hidden.isChecked(),
            "crc_after_upload": crc.isChecked(),
            "language": language.currentText(),
            "theme": theme_box.currentData(),
        }
    )


@dataclass(frozen=True)
class _Clip:
    """The window's one clipboard: where the entries were marked and whether they are copied or moved.
    `items` are Local names or Next entries, according to `side`."""

    side: str
    folder: str
    items: list
    mode: str  # "copy" or "cut"


CARD_ICON = "gamepad-2"  # the waiting card's icon


class _Operation(QObject):
    progress = Signal(str, int)
    finished = Signal(object)  # transfer.Result, or the exception that ended it
    checked = Signal(object)  # the collisions a batch would cause, or the exception that stopped the check
    disconnected = Signal()  # the Next was told to leave (or the wait ran out)


class MainWindow(QMainWindow):
    def __init__(
        self,
        listener: Listener,
        local_addresses: Callable[[], list[tuple[str, str]]] = local_ipv4_addresses,
        ask_name: Callable[[str, str], str | None] = _ask_name_dialog,
        confirm_delete: Callable[[str], bool] = _confirm_delete_dialog,
        confirm_overwrite: Callable[[str, int], tuple[str, bool]] = _confirm_overwrite_dialog,
        settings_path: Path | None = None,
        ask_settings: Callable[[Settings], Settings | None] = _settings_dialog,
        local_roots: Callable[[], list[Root]] = local_roots,
        show_about: Callable[[], None] = _about_dialog,
        trash: Trash = system_trash,
        confirm_permanent: Callable[[str], bool] = _confirm_permanent_dialog,
        color_scheme: Callable[[], Qt.ColorScheme] = theme.system_scheme,
    ):
        super().__init__()
        self._color_scheme = color_scheme
        self._theme_name = "light"
        self._address = ""
        self._then: Callable | None = None
        self._trash, self._confirm_permanent = trash, confirm_permanent
        self._show_about = show_about
        self._active = LOCAL  # the pane that last had focus: the actions apply to it
        # Without a path nothing is read or written (tests, throwaway windows).
        self._settings_path = settings_path
        self._settings = settings_store.load(settings_path) if settings_path else Settings()
        self._ask_settings = ask_settings
        self._ask_name, self._confirm_delete = ask_name, confirm_delete
        self._confirm_overwrite = confirm_overwrite
        self._after_check: Callable | None = None
        self.setWindowTitle("nexplorer")
        self._local_addresses = local_addresses

        self._next_pane = NextPane()
        self._card = self._build_waiting_card()
        self._next_pane.show_card(self._card)
        self._state = "waiting"

        root = QWidget()
        start = self._settings.local_folder
        self._local_pane = LocalPane(start if os.path.isdir(start) else os.path.expanduser("~"), local_roots)
        self._next_pane.preferred_path = self._settings.next_folder
        self._local_pane.set_sort(self._settings.local_sort)
        self._next_pane.set_sort(self._settings.next_sort)
        self._local_pane.set_show_hidden(self._settings.show_hidden)
        self._next_pane.set_show_hidden(self._settings.show_hidden)
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._local_pane)
        self._centre = self._build_centre_column()
        self._splitter.addWidget(self._centre)
        self._splitter.addWidget(self._next_pane)
        self._splitter.setCollapsible(1, False)
        self.set_splitter_sizes(list(self._settings.splitter) or [1, 1])
        panes_page = QWidget()
        page = QHBoxLayout(panes_page)
        page.setContentsMargins(0, 0, 0, 0)
        page.addWidget(self._splitter)
        self._compare_view = CompareView()
        self._views = QStackedWidget()
        self._views.addWidget(panes_page)
        self._views.addWidget(self._compare_view)

        self._actions = SharedActions(self, lambda: self._active)
        self._define_actions()
        self._build_menus()
        self._build_toolbar()
        self.refresh_theme()
        QApplication.styleHints().colorSchemeChanged.connect(self._on_scheme_changed)

        self._op_label = QLabel()
        self._op_bar = QProgressBar()
        self._op_bar.setMaximumHeight(12)
        self._op_bar.setTextVisible(False)
        self._cancel_button = QPushButton(tr("Cancel"))
        self._cancel_button.clicked.connect(self._cancel_operation)
        self._op_row = QWidget()
        op = QHBoxLayout(self._op_row)
        op.setContentsMargins(0, 0, 0, 0)
        op.addWidget(self._op_label, 1)
        op.addWidget(self._op_bar, 2)
        op.addWidget(self._cancel_button)
        self._summary = QLabel()
        self._summary.setTextFormat(Qt.PlainText)
        self._connection = QLabel()
        self._selection = QLabel()
        self._selection.setTextFormat(Qt.PlainText)
        self._dot_notice = QLabel()
        self._dot_notice.setTextFormat(Qt.PlainText)
        self._dot_notice.hide()
        self._capabilities = Capabilities()
        self._fresh_rows = None  # compared rows recomputed by a transfer, shown when it ends
        self._version_known = False
        self._op_row.hide()
        self._busy = False
        self._cancel = threading.Event()
        self._operation = _Operation()
        self._operation.progress.connect(self._on_progress)
        self._operation.finished.connect(self._on_finished)
        self._disconnecting = False
        self._clipboard: _Clip | None = None
        self._clear_clipboard_if_clean = False
        self._operation.disconnected.connect(self._on_disconnected)
        self._operation.checked.connect(self._on_checked)
        self._next_pane.selection_changed.connect(self._update_actions)
        self._local_pane.selection_changed.connect(self._update_actions)
        for side in (LOCAL, NEXT):
            pane = self._pane(side)
            pane.focused.connect(lambda side=side: self.activate_pane(side))
            pane.context_requested.connect(lambda row, pos, side=side: self._popup_context(side, row, pos))
        self._local_pane.file_activated.connect(self.send_file)
        self._next_pane.file_activated.connect(self.receive_file)
        self._local_pane.set_active(True)
        self._local_pane.selection_changed.connect(lambda: self._show_selection(self._local_pane))
        self._next_pane.selection_changed.connect(lambda: self._show_selection(self._next_pane))

        column = QVBoxLayout(root)
        column.addWidget(self._views, 1)
        self.setCentralWidget(root)
        bar = self.statusBar()
        bar.addWidget(self._connection)
        bar.addWidget(self._summary, 1)
        bar.addWidget(self._dot_notice)
        bar.addPermanentWidget(self._op_row)
        bar.addPermanentWidget(self._selection)
        self.setMinimumSize(800, 450)
        self.resize(1100, 650)
        if self._settings.geometry:
            self.restoreGeometry(base64.b64decode(self._settings.geometry))

        self._show_waiting()
        self._listener = listener
        self._bridge = ListenerBridge(listener)
        self._bridge.session_started.connect(self._show_connected)

        self._compare_view.transfer_requested.connect(self.compare_transfer)
        self._compare_view.apply_requested.connect(self.compare_apply)
        self._compare_view.verify_requested.connect(self.compare_verify)
        self._compare_view.back_requested.connect(self.compare_back)
        self._compare_view.expand_requested.connect(self.compare_expand)
        self._compare_view.scan_all_requested.connect(self.compare_scan_all)
        self._next_pane.files_dropped.connect(self.drop_files)
        self._local_pane.next_entries_dropped.connect(lambda names, _row: self.drop_next_entries(names))
        self._next_pane.entries_moved.connect(self.move_dropped)
        self._local_pane.local_entries_dropped.connect(self.drop_local_entries)
        self._bridge.session_ready.connect(self._next_pane.bind)
        self._bridge.session_ready.connect(lambda _s: self._update_actions())
        self._bridge.dot_version.connect(self._on_dot_version)
        self._bridge.dot_unanswered.connect(self._on_dot_unanswered)
        self._bridge.session_ended.connect(self._show_waiting)

    # -- actions, menus
    def _define_actions(self) -> None:
        """Every action once; a later ticket gives an action its Local side with `bind`."""
        a = self._actions

        def idle() -> bool:
            return self._next_pane.session() is not None and not self._busy

        def selected() -> int:
            return len(self._next_pane.selected_names())

        def can_copy() -> bool:
            return idle() and self._capabilities.copy

        def always() -> bool:
            return True

        def connected() -> bool:
            return self._next_pane.session() is not None

        def at_rest() -> bool:
            return not self._busy

        def sort(key: str) -> Callable[[], None]:
            return lambda: self._pane(self._active).sort_by(key)

        a.define("new_folder", tr("New folder"), "Ctrl+Shift+N", next=Binding(idle, self.new_folder))
        a.define(
            "rename",
            tr("Rename"),
            "F2",
            next=Binding(lambda: idle() and self._capabilities.rename and selected() == 1, self.rename_selected),
        )
        a.define("delete", tr("Delete"), "Del", next=Binding(lambda: idle() and selected() >= 1, self.delete_selected))
        a.define("settings", tr("Settings"), both=Binding(always, self.open_settings))
        a.define("quit", tr("Quit"), "Ctrl+Q", both=Binding(always, self.close))
        a.define("copy", tr("Copy"), "Ctrl+C", next=Binding(lambda: can_copy() and selected() >= 1, self.copy_selected))
        a.define("cut", tr("Cut"), "Ctrl+X", next=Binding(lambda: can_copy() and selected() >= 1, self.cut_selected))
        a.define(
            "paste", tr("Paste"), "Ctrl+V", next=Binding(lambda: self._can_paste(NEXT), self.paste)
        )
        a.define(
            "select_all",
            tr("Select all"),
            "Ctrl+A",
            local=Binding(always, self._local_pane.select_all),
            next=Binding(lambda: connected() and at_rest(), self._next_pane.select_all),
        )
        def local_selected() -> bool:
            return bool(self._local_pane.selected_names())

        a.define("send", tr("Send"), both=Binding(lambda: idle() and local_selected(), self.send_selected))
        a.define("receive", tr("Receive"), both=Binding(lambda: idle() and selected() >= 1, self.receive_selected))
        a.define(  # F5: the active pane's selection goes to the other side; not in a menu
            "transfer",
            tr("Transfer"),
            "F5",
            local=Binding(lambda: idle() and local_selected(), self.send_selected),
            next=Binding(lambda: idle() and selected() >= 1, self.receive_selected),
        )
        self.addAction(a.action("transfer"))
        a.define("compare", tr("Compare"), both=Binding(idle, self.compare))
        a.define(
            "disconnect",
            tr("Disconnect"),
            both=Binding(lambda: connected() and not self._disconnecting, self.disconnect),
        )
        a.define("show_hidden", tr("Show hidden files"), both=Binding(always, self._toggle_hidden), checkable=True)
        for key, label in (("name", tr("Name")), ("size", tr("Size")), ("type", tr("Type"))):
            a.define(f"sort_{key}", label, local=Binding(always, sort(key)), next=Binding(at_rest, sort(key)))
        a.define(
            "refresh",
            tr("Refresh"),
            "Ctrl+R",
            local=Binding(always, lambda: self._local_pane.reload()),
            next=Binding(lambda: connected() and at_rest(), lambda: self._next_pane.reload()),
        )
        a.define("about", tr("About"), both=Binding(always, self._show_about))
        self._bind_local_actions()

    def _build_centre_column(self) -> QWidget:
        """Send (right arrow) and Receive (left arrow) between the panes; they follow the
        enablement of the shared actions."""
        column = QWidget()
        column.setFixedWidth(52)
        layout = QVBoxLayout(column)
        layout.addStretch(1)
        self._send_button, self._receive_button = QPushButton("\u2192"), QPushButton("\u2190")
        for button, key, text in ((self._send_button, "send", tr("Send")), (self._receive_button, "receive", tr("Receive"))):
            button.setToolTip(text)
            button.setAccessibleName(text)
            button.clicked.connect(lambda _c=False, key=key: self._actions.action(key).trigger())
            layout.addWidget(button)
        layout.addStretch(1)
        return column

    def _build_menus(self) -> None:
        a = self._actions.action
        bar = self.menuBar()
        for title, keys in (
            (tr("File"), ["new_folder", "rename", "delete", "settings", "quit"]),
            (tr("Edit"), ["copy", "cut", "paste", "select_all"]),
            (tr("Transfer"), ["send", "receive", "compare", "disconnect"]),
            (tr("View"), ["show_hidden", "sort", "refresh"]),
            (tr("Help"), ["about"]),
        ):
            menu = bar.addMenu(title)
            for key in keys:
                if key == "sort":
                    sub = menu.addMenu(tr("Sort by"))
                    for sort_key in ("sort_name", "sort_size", "sort_type"):
                        sub.addAction(a(sort_key))
                else:
                    menu.addAction(a(key))

    def _build_toolbar(self) -> None:
        """The frequent actions under the menu bar: the shared actions themselves, so labels,
        shortcuts and enablement are those of the menus."""
        self._toolbar = QToolBar(tr("Toolbar"), self)
        self._toolbar.setObjectName("toolbar")
        self._toolbar.setMovable(False)
        self._toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        for key in icons.TOOLBAR_ACTIONS:
            if key is None:
                self._toolbar.addSeparator()
            else:
                self._toolbar.addAction(self._actions.action(key))
        self.addToolBar(Qt.TopToolBarArea, self._toolbar)

    def refresh_theme(self) -> None:
        """Apply the Theme setting application-wide and tint icons and Compare colours to it."""
        self._theme_name = theme.apply(QApplication.instance(), self._settings.theme, self._color_scheme())
        self.set_icon_colour(theme.icon_colour(self._theme_name))
        self._compare_view.set_theme(self._theme_name)
        self._local_pane.set_theme(self._theme_name)
        self._next_pane.set_theme(self._theme_name)
        self._show_connection()

    def current_theme(self) -> str:
        """The palette in use: light or dark (System resolved)."""
        return self._theme_name

    def _on_scheme_changed(self, *_args) -> None:
        if self._settings.theme == "system":
            self.refresh_theme()

    def set_icon_colour(self, colour) -> None:
        """Tint every icon (actions and list rows) with `colour`; None for the palette text colour."""
        for key, name in icons.ACTION_ICONS.items():
            self._actions.action(key).setIcon(icons.icon(name, colour))
        self._local_pane.set_icon_colour(colour)
        self._next_pane.set_icon_colour(colour)
        self._card_icon.setPixmap(icons.icon(CARD_ICON, colour).pixmap(48, 48))
        self._compare_view.set_icon_colour(colour)

    def toolbar_action_keys(self) -> list[str | None]:
        """The shared action behind each toolbar button (None for a separator)."""
        by_object = {id(self._actions.action(k)): k for k in icons.ACTION_ICONS}
        return [None if a.isSeparator() else by_object[id(a)] for a in self._toolbar.actions()]

    def toolbar_entries(self) -> list[tuple[str, bool, bool]]:
        """(tooltip text, enabled, has an icon) of each toolbar button."""
        return [(a.text(), a.isEnabled(), not a.icon().isNull()) for a in self._toolbar.actions() if not a.isSeparator()]

    def menu_entry_has_icon(self, title: str, label: str) -> bool:
        return not next(a for a in self._menu(title).actions() if a.text() == label).icon().isNull()

    def _pane(self, side: str):
        return self._local_pane if side == LOCAL else self._next_pane

    def activate_pane(self, side: str) -> None:
        """The pane the actions apply to: the one that last had focus."""
        self._active = side
        self._local_pane.set_active(side == LOCAL)
        self._next_pane.set_active(side == NEXT)
        self._update_actions()

    def active_pane(self) -> str:
        return self._active

    def _toggle_hidden(self) -> None:
        self.apply_settings(replace(self._settings, show_hidden=not self._settings.show_hidden))
        self._write_settings()

    ROW_ACTIONS = ("copy", "cut", "paste", "rename", "delete")
    EMPTY_ACTIONS = ("new_folder", "paste", "select_all", "refresh")

    def context_menu(self, side: str, row: str | None) -> QMenu:
        """The right-click menu of `side` on `row` (None for empty space). The pane becomes
        active, and an unselected row is selected first."""
        self._pane(side).prepare_context(row or "")
        self.activate_pane(side)
        menu = QMenu(self)
        for key in self.ROW_ACTIONS if row else self.EMPTY_ACTIONS:
            menu.addAction(self._actions.action(key))
        return menu

    def _popup_context(self, side: str, row: str, pos) -> None:
        self.context_menu(side, row or None).exec(pos)

    def _build_waiting_card(self) -> QWidget:
        """The centred card shown in place of the ZX Spectrum Next list while nothing is connected."""
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setObjectName("card")
        icon = self._card_icon = QLabel()
        icon.setAlignment(Qt.AlignCenter)
        title = QLabel(tr("Waiting for a ZX Spectrum Next"))
        title.setStyleSheet("font-weight: bold")
        title.setAlignment(Qt.AlignCenter)
        self._card_addresses = QLabel()
        self._card_addresses.setTextFormat(Qt.PlainText)
        self._card_addresses.setAlignment(Qt.AlignCenter)
        run = QLabel(tr("On the ZX Spectrum Next, run:"))
        run.setAlignment(Qt.AlignCenter)
        self._card_command = QLabel(SYNC_COMMAND)
        self._card_command.setStyleSheet("font-family: monospace")
        self._card_command.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._copy_button = QPushButton(tr("Copy"))
        self._copy_button.clicked.connect(lambda: QApplication.clipboard().setText(SYNC_COMMAND))
        command_row = QHBoxLayout()
        command_row.addStretch(1)
        command_row.addWidget(self._card_command)
        command_row.addWidget(self._copy_button)
        command_row.addStretch(1)
        reminder = QLabel(tr("The Local address must match the one in") + f" {CONFIG_FILE}")
        reminder.setWordWrap(True)
        reminder.setAlignment(Qt.AlignCenter)
        self._card_labels = [title, self._card_addresses, run, self._card_command, reminder]
        inner = QVBoxLayout(card)
        for widget in (icon, title, self._card_addresses, run):
            inner.addWidget(widget)
        inner.addLayout(command_row)
        inner.addWidget(reminder)
        outer = QWidget()
        centred = QVBoxLayout(outer)
        centred.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(card, 4)
        row.addStretch(1)
        centred.addLayout(row)
        centred.addStretch(1)
        return outer

    def _show_selection(self, pane) -> None:
        """The status bar summarises the selection of the pane that changed last."""
        entries = pane.selected_entries()
        if not entries:
            self._selection.setText("")
            return
        noun = tr("item") if len(entries) == 1 else tr("items")
        self._selection.setText(f"{len(entries)} {noun}, {format_size(sum(e.size for e in entries))}")

    def _on_dot_version(self, version: str) -> None:
        """The dot announced its version ("" when it did not answer `Y`): grey what it lacks."""
        self._capabilities = capabilities(version or None)
        self._version_known = True
        missing = not self._capabilities.complete
        text = tr("The dot on the ZX Spectrum Next is too old for some actions: update .sync5 to version") + f" {MINIMUM_DOT}"
        self._dot_notice.setText(text if missing else "")
        self._dot_notice.setVisible(missing)
        self._update_actions()

    def _on_dot_unanswered(self) -> None:
        """`Y` got no answer in time: the dot is not proven old, so nothing is greyed."""
        self._capabilities = Capabilities()
        self._version_known = True
        self._dot_notice.setText("")
        self._dot_notice.hide()
        self._update_actions()

    def _show_waiting(self) -> None:
        self._capabilities = Capabilities()
        self._version_known = False
        self._dot_notice.setText("")
        self._dot_notice.hide()
        if self._clipboard is not None and self._clipboard.side == NEXT:
            self._clipboard = None
        self._next_pane.unbind()
        self._card_addresses.setText("\n".join(f"{name}: {ip}" for name, ip in self._local_addresses()))
        self._connection.setText(tr("Not connected"))
        self._next_pane.set_controls_enabled(False)
        self._next_pane.show_card(self._card)
        self._state = "waiting"
        self._update_actions()

    def _show_connected(self, address: str) -> None:
        self._address = address
        self._state = "connected"
        self._show_connection()
        self._next_pane.set_controls_enabled(True)
        self._next_pane.show_list()

    def _show_connection(self) -> None:
        """The status-bar connection text, its dot in the palette's `connected` colour."""
        if self._state != "connected":
            return
        dot = theme.PALETTES[self._theme_name]["connected"]
        self._connection.setText(f'<span style="color:{dot}">\u25cf</span> {tr("Connected")} \u2014 {self._address}')

    # -- send and receive
    def send_selected(self) -> None:
        """Send the selected Local entries to the Next folder shown."""
        session = self._next_pane.session()
        paths = [os.path.join(self._local_pane.path(), e.name) for e in self._local_pane.selected_entries()]
        folder = self._next_pane.path()
        if session and paths and folder:
            self._send_checked(session, paths, folder)

    def send_file(self, name: str) -> None:
        """Double-click on a Local file: send it to the Next folder shown."""
        session, folder = self._next_pane.session(), self._next_pane.path()
        if session and folder and not self._busy:
            self._send_checked(session, [os.path.join(self._local_pane.path(), name)], folder)

    def receive_file(self, name: str) -> None:
        """Double-click on a Next file: receive it into the Local folder shown."""
        session = self._next_pane.session()
        entries = [e for e in self._next_pane.entries() if e.name == name and not e.is_dir]
        source, target = self._next_pane.path(), self._local_pane.path()
        if session and entries and source and target and not self._busy:
            self._receive_checked(session, source, entries, target)

    def drop_files(self, paths: list[str], subfolder: str = "") -> None:
        """Files dropped on the Next pane: send them into the folder shown, or the subfolder hit."""
        session, folder = self._next_pane.session(), self._next_pane.folder_path(subfolder)
        if session and paths and folder:
            self._send_checked(session, paths, folder)

    def drop_next_entries(self, names: list[str]) -> None:
        """Next entries dragged onto the Local pane: receive them into the Local folder shown."""
        session = self._next_pane.session()
        wanted = set(names)
        entries = [e for e in self._next_pane.entries() if e.name in wanted]
        source, target = self._next_pane.path(), self._local_pane.path()
        if session and entries and source and target:
            self._receive_checked(session, source, entries, target)

    def receive_selected(self) -> None:
        """Receive the selected Next entries into the Local folder shown."""
        session = self._next_pane.session()
        entries = self._next_pane.selected_entries()
        source, target = self._next_pane.path(), self._local_pane.path()
        if session and entries and source and target:
            self._receive_checked(session, source, entries, target)

    # -- overwrite check
    def _send_checked(self, session, paths: list[str], folder: str) -> None:
        verify = self._settings.crc_after_upload and self._capabilities.crc
        self._checked_run(
            lambda: overwrite.send_collisions(session, paths, folder),
            lambda skip: lambda progress, cancel: send(
                session, paths, folder, progress, cancel, verify_crc=verify, skip=skip
            ),
        )

    def _receive_checked(self, session, source: str, entries: list, target: str) -> None:
        self._checked_run(
            lambda: overwrite.receive_collisions(session, source, entries, target),
            lambda skip: lambda progress, cancel: receive(
                session, source, entries, target, progress, cancel, skip=skip
            ),
        )

    def _checked_run(self, check: Callable, make_work: Callable) -> None:
        """List the destination off the UI thread, ask about what exists, then run the batch.
        A destination that cannot be listed refuses the batch."""
        if self._busy:
            return
        self._busy = True
        self._cancel.clear()  # the Cancel button also stops a check that is still listing
        self._cancel_button.setEnabled(True)
        self._cancel_button.setText(tr("Cancel"))
        self._summary.setText("")
        self._op_bar.setValue(0)
        self._op_label.setText("")
        self._op_row.show()
        self._after_check = make_work
        self._update_actions()
        operation = self._operation

        def thread() -> None:
            try:
                outcome = check()
            except Exception as exc:  # noqa: BLE001 - shown to the user
                outcome = exc
            self._emit(operation.checked, outcome)

        threading.Thread(target=thread, daemon=True).start()

    def _on_checked(self, outcome) -> None:
        make_work, self._after_check = self._after_check, None
        self._busy = False
        self._op_row.hide()
        if self._cancel.is_set():
            self._summary.setText(tr("Cancelled"))
        elif isinstance(outcome, Exception) or make_work is None:
            self._summary.setText(f"{tr('Not started, the destination cannot be checked')}: {outcome}")
        else:
            decision = overwrite.decide(outcome, self._confirm_overwrite)
            if decision.cancelled:
                self._summary.setText(tr("Cancelled"))
            else:
                self._run(make_work(decision.skip))
        self._update_actions()

    # -- changes on the Next
    def new_folder(self) -> None:
        """Ask for a name and create that folder in the Next folder shown."""
        session, folder = self._next_pane.session(), self._next_pane.path()
        if not session or not folder or self._busy:
            return
        name = self._ask_name(tr("New folder"), "")
        if name and self._plain(name):
            self._run(lambda progress, cancel: make_folder(session, folder, name))

    def rename_selected(self) -> None:
        """Rename the one selected Next entry."""
        session, folder = self._next_pane.session(), self._next_pane.path()
        entries = self._next_pane.selected_entries()
        if not session or not folder or len(entries) != 1 or self._busy:
            return
        old = entries[0].name
        new = self._ask_name(tr("Rename"), old)
        if new and new != old and self._plain(new):
            self._run(lambda progress, cancel: rename(session, folder, old, new))

    def copy_selected(self) -> None:
        """Mark the selected Next entries to be copied by the next paste."""
        self._mark("copy")

    def cut_selected(self) -> None:
        """Mark the selected Next entries to be moved by the next paste."""
        self._mark("cut")

    def _mark(self, mode: str) -> None:
        entries = self._next_pane.selected_entries()
        if self._next_pane.session() is not None and entries and self._capabilities.copy:
            self._clipboard = _Clip(NEXT, self._next_pane.path(), entries, mode)
            self._update_actions()

    def _can_paste(self, side: str) -> bool:
        """Paste on `side`: inside the side where the entries were marked, or across, for a copy only."""
        clip = self._clipboard
        if clip is None or self._busy:
            return False
        connected = self._next_pane.session() is not None
        if clip.side == side:
            return connected and self._capabilities.copy if side == NEXT else True
        return clip.mode == "copy" and connected

    def paste(self) -> None:
        """Paste on the Next pane: copy or move the marked entries into the Next folder shown, or
        send the copied Local entries there."""
        session, target, clip = self._next_pane.session(), self._next_pane.path(), self._clipboard
        if not session or not target or clip is None or not self._can_paste(NEXT):
            return
        if clip.side == LOCAL:
            self._send_checked(session, [os.path.join(clip.folder, n) for n in clip.items], target)
            return
        action = move if clip.mode == "cut" else copy
        self._clear_clipboard_if_clean = clip.mode == "cut"  # a failed move can be retried
        self._run(lambda progress, cancel: action(session, clip.folder, clip.items, target, progress, cancel))

    def move_dropped(self, names: list[str], row: str) -> None:
        """Next entries dropped on a folder row of the Next pane: move them into that folder."""
        session, source = self._next_pane.session(), self._next_pane.path()
        target = self._next_pane.folder_path(row) if row else ""
        wanted = set(names)
        entries = [e for e in self._next_pane.entries() if e.name in wanted]
        if session and source and target and target != source and entries and self._capabilities.copy:
            self._clear_clipboard_if_clean = False
            self._run(lambda progress, cancel: move(session, source, entries, target, progress, cancel))

    def _plain(self, name: str) -> bool:
        if is_plain_name(name):
            return True
        self._summary.setText(f"{tr('Invalid name')}: {name}")
        return False

    def delete_selected(self) -> None:
        """Delete the selected Next entries, folders with their content, once confirmed."""
        session, folder = self._next_pane.session(), self._next_pane.path()
        entries = self._next_pane.selected_entries()
        if not session or not folder or not entries or self._busy:
            return
        message = (
            f"{tr('Delete')} {len(entries)} {tr('items')} {tr('from the ZX Spectrum Next')}, {tr('starting with')} \u00ab{entries[0].name}\u00bb?\n"
            + tr("The deletion is permanent: the ZX Spectrum Next has no trash.")
        )
        if self._confirm_delete(message):
            self._run(lambda progress, cancel: remove(session, folder, entries, progress, cancel))

    # -- changes on Local (the operations live in `local_ops`)
    def _bind_local_actions(self) -> None:
        a = self._actions

        def free() -> bool:
            return not self._busy

        def selected() -> int:
            return len(self._local_pane.selected_names())

        for key, enabled, run in (
            ("new_folder", free, self.local_new_folder),
            ("rename", lambda: free() and selected() == 1, self.local_rename),
            ("delete", lambda: free() and selected() >= 1, self.local_delete),
            ("copy", lambda: free() and selected() >= 1, lambda: self._local_mark("copy")),
            ("cut", lambda: free() and selected() >= 1, lambda: self._local_mark("cut")),
            ("paste", lambda: self._can_paste(LOCAL), self.local_paste),
        ):
            a.bind(key, LOCAL, Binding(enabled, run))

    def local_new_folder(self) -> None:
        folder = self._local_pane.path()
        name = self._ask_name(tr("New folder"), "") if folder and not self._busy else None
        if name and self._plain(name):
            self._run(lambda progress, cancel: local_ops.make_folder(folder, name))

    def local_rename(self) -> None:
        folder, names = self._local_pane.path(), self._local_pane.selected_names()
        if not folder or len(names) != 1 or self._busy:
            return
        new = self._ask_name(tr("Rename"), names[0])
        if new and new != names[0] and self._plain(new):
            self._run(lambda progress, cancel: local_ops.rename(folder, names[0], new))

    def _local_mark(self, mode: str) -> None:
        names = self._local_pane.selected_names()
        if names:
            self._clipboard = _Clip(LOCAL, self._local_pane.path(), names, mode)
            self._update_actions()

    def local_paste(self) -> None:
        """Copy or move the marked Local entries into the Local folder shown."""
        target, clip = self._local_pane.path(), self._clipboard
        if not target or clip is None or not self._can_paste(LOCAL):
            return
        if clip.side == NEXT:
            self._receive_checked(self._next_pane.session(), clip.folder, clip.items, target)
            return
        action = local_ops.move if clip.mode == "cut" else local_ops.copy
        self._clear_clipboard_if_clean = clip.mode == "cut"  # a failed move can be retried
        self._run(lambda progress, cancel: action(clip.folder, clip.items, target, progress, cancel))

    def drop_local_entries(self, names: list[str], row: str, copy: bool = False) -> None:
        """Local entries dropped on a folder row of the Local pane: move them (Shift: copy)."""
        source = self._local_pane.path()
        target = self._local_pane.folder_path(row) if row else ""
        if not source or not target or row in names or self._busy:
            return
        action = local_ops.copy if copy else local_ops.move
        self._clear_clipboard_if_clean = False
        self._run(lambda progress, cancel: action(source, names, target, progress, cancel))

    def local_delete(self) -> None:
        """Send the selected Local entries to the trash once confirmed; what the trash cannot
        take can be deleted for good, after a second confirmation."""
        folder, names = self._local_pane.path(), self._local_pane.selected_names()
        if not folder or not names or self._busy:
            return
        message = (
            f"{tr('Delete')} {len(names)} {tr('items')} {tr('to the trash')}, "
            f"{tr('starting with')} \u00ab{names[0]}\u00bb?"
        )
        if not self._confirm_delete(message):
            return

        def trashed(outcome) -> None:
            failures = outcome.failures if isinstance(outcome, Result) else []
            if failures and self._confirm_permanent(
                f"{tr('The trash cannot take')} {len(failures)} {tr('items')}:\n"
                + "\n".join(f"\u00ab{f.name}\u00bb: {f.reason}" for f in failures)
                + f"\n{tr('Delete them permanently?')}"
            ):
                failed = [f.name for f in failures]
                self._run(lambda progress, cancel: local_ops.delete_entries(folder, failed, progress, cancel))

        self._run(lambda progress, cancel: local_ops.trash_entries(folder, names, self._trash, progress, cancel), trashed)

    # -- compare
    def compare(self) -> None:
        """Replace the panes with the Differences between the two folders they show."""
        session = self._next_pane.session()
        local_dir, next_dir = self._local_pane.path(), self._next_pane.path()
        if not session or not local_dir or not next_dir or self._busy:
            return
        rows = compare_level(
            self._local_pane.entries(),
            self._next_pane.entries(),
            next_dir,
            read_ignore(local_dir),
            self._settings.show_hidden,
        )
        self._compare_view.show_rows(f"{local_dir}  \u2194  {next_dir}", rows)
        self._views.setCurrentWidget(self._compare_view)
        self._update_actions()

    def compare_state_texts(self) -> dict[str, str]:
        return self._compare_view.state_texts()

    def compare_state_colour(self, path: str):
        return self._compare_view.state_colour(path)

    def compare_back(self) -> None:
        self._views.setCurrentIndex(0)
        self._update_actions()

    def compare_transfer(self, name: str) -> None:
        """Transfer one row on its own, whatever its checkbox."""
        row = self._compare_view.row(name)
        *parents, _ = name.split("/")
        local_dir, next_dir = self._local_pane.path(), self._next_pane.path()
        if local_dir and next_dir:
            self._apply_rows(
                [_one_row(row)], os.path.join(local_dir, *parents), "/".join([next_dir.rstrip("/"), *parents])
            )

    def compare_apply(self) -> None:
        """Transfer every checked row, one after the other."""
        self._apply_rows(self._compare_view.rows(), self._local_pane.path(), self._next_pane.path())

    def compare_verify(self) -> None:
        """Ask the Next for the CRC-32 of the same-size files and settle their rows."""
        session = self._next_pane.session()
        local_dir, next_dir = self._local_pane.path(), self._next_pane.path()
        rows = self._compare_view.rows()
        if session and local_dir and next_dir and self._capabilities.crc:
            self._run(lambda _progress, cancel: verify_rows(session, local_dir, next_dir, rows, cancel))

    def _apply_rows(self, rows: list, local_dir: str, next_dir: str) -> None:
        """Transfer `rows`, which live in the given folders, then recompute the compared rows."""
        session = self._next_pane.session()
        top_local, top_next = self._local_pane.path(), self._next_pane.path()
        verify = self._settings.crc_after_upload and self._capabilities.crc
        hidden, ignore = self._settings.show_hidden, read_ignore(top_local) if top_local else []
        shown = self._compare_view.rows()
        if session and local_dir and next_dir and top_local and top_next:

            def work(progress, cancel):
                result = apply_rows(session, local_dir, next_dir, rows, progress, cancel, verify_crc=verify)
                try:
                    self._fresh_rows = recompare(session, shown, top_local, top_next, hidden, ignore)
                except (OSError, RemoteError, ConnectionError, TimeoutError):
                    pass  # the rows stay as they were
                return result

            self._run(work)

    def compare_expand(self, path: str) -> None:
        """List the next level of a not scanned folder, given as a path from the compared folders."""
        session = self._next_pane.session()
        local_dir, next_dir = self._local_pane.path(), self._next_pane.path()
        if not session or not local_dir or not next_dir or self._busy:
            return
        *parents, _ = path.split("/")
        row = self._compare_view.row(path)
        local_dir, next_dir = os.path.join(local_dir, *parents), "/".join([next_dir.rstrip("/"), *parents])
        hidden, ignore = self._settings.show_hidden, read_ignore(self._local_pane.path())

        def work(progress, cancel):
            expand_row(session, row, local_dir, next_dir, hidden, ignore)
            return Result()

        self._run(work)

    def compare_scan_all(self) -> None:
        """Expand the whole tree, with progress; Cancel leaves the unreached folders not scanned."""
        session = self._next_pane.session()
        local_dir, next_dir = self._local_pane.path(), self._next_pane.path()
        if not session or not local_dir or not next_dir or self._busy:
            return
        rows, hidden = self._compare_view.rows(), self._settings.show_hidden
        ignore = read_ignore(local_dir)
        self._run(
            lambda progress, cancel: scan_all(session, rows, local_dir, next_dir, progress, cancel, hidden, ignore)
        )

    def compare_states(self) -> list[tuple[str, str]]:
        """(path, state) of every row shown, nested ones included."""
        found: list[tuple[str, str]] = []

        def walk(rows, prefix):
            for r in rows:
                found.append((prefix + r.name, r.state))
                walk(r.children or [], prefix + r.name + "/")

        walk(self._compare_view.rows(), "")
        return found

    def compare_reverse(self, name: str) -> None:
        self._compare_view.reverse(name)

    def compare_set_checked(self, name: str, checked: bool) -> None:
        self._compare_view.set_checked(name, checked)

    def compare_active(self) -> bool:
        return self._views.currentWidget() is self._compare_view

    def compare_rows(self) -> list[tuple[str, str, str, bool]]:
        return [(r.name, r.state, r.direction or "", r.checked) for r in self._compare_view.rows()]

    def _run(self, work: Callable, then: Callable | None = None) -> None:
        """Run one modifying operation off the UI thread; only one at a time. `then` receives
        the outcome on the UI thread once the operation is shown as finished."""
        if self._busy:
            return
        self._busy = True
        self._then = then
        self._cancel.clear()
        self._cancel_button.setEnabled(True)
        self._cancel_button.setText(tr("Cancel"))
        self._summary.setText("")
        self._op_bar.setValue(0)
        self._op_label.setText("")
        self._op_row.show()
        self._update_actions()
        operation, cancel = self._operation, self._cancel

        def thread() -> None:
            try:
                outcome = work(lambda name, pct: self._emit(operation.progress, name, pct), cancel.is_set)
            except Exception as exc:  # noqa: BLE001 - shown to the user
                outcome = exc
            self._emit(operation.finished, outcome)

        threading.Thread(target=thread, daemon=True).start()

    def _emit(self, signal, *args) -> None:
        try:
            signal.emit(*args)
        except RuntimeError:  # the window is already gone
            pass

    def disconnect(self) -> None:
        """End the Session (the Next quits its dot) and go back to waiting; the window stays."""
        if self._next_pane.session() is None or self._disconnecting:
            return
        self._disconnecting = True
        self._cancel.set()
        self._update_actions()
        listener, operation = self._listener, self._operation

        def thread() -> None:
            listener.end_session()
            self._emit(operation.disconnected)

        threading.Thread(target=thread, daemon=True).start()

    def _on_disconnected(self) -> None:
        self._disconnecting = False
        self._update_actions()

    def _cancel_operation(self) -> None:
        self._cancel.set()
        self._cancel_button.setEnabled(False)  # seen: a get only stops at the end of its file
        self._cancel_button.setText(tr("Cancelling") + "\u2026")

    def _on_progress(self, name: str, percent: int) -> None:
        self._op_label.setText(name)
        self._op_bar.setValue(percent)

    def _on_finished(self, outcome) -> None:
        self._busy = False
        self._op_row.hide()
        if isinstance(outcome, Result) and self._clear_clipboard_if_clean and not (
            outcome.failures or outcome.cancelled
        ):
            self._clipboard = None
        self._clear_clipboard_if_clean = False
        self._show_outcome(outcome)
        self._next_pane.reload()
        self._local_pane.reload()
        if self._fresh_rows is not None:
            self._compare_view.set_rows(self._fresh_rows)
            self._fresh_rows = None
        self._compare_view.refresh()
        self._update_actions()
        then, self._then = self._then, None
        if then is not None:
            then(outcome)

    def _show_outcome(self, outcome) -> None:
        """The summary line: how an operation ended, one line per entry that failed."""
        if isinstance(outcome, Result):
            lines = [f"{f.name}: {f.reason}" for f in outcome.failures]
            head = tr("Cancelled") if outcome.cancelled else tr("Done")
            if outcome.dropped:
                head = tr("Session lost, operation stopped")
            if lines:
                head += f" \u2014 {len(lines)} " + tr("failed")
            self._summary.setText("\n".join([head, *lines]))
        else:
            self._summary.setText(f"{tr('Failed')}: {outcome}")

    def _update_actions(self) -> None:
        """Actions follow the active pane, the Session, the capabilities and the selection,
        and are greyed while one operation runs."""
        self._actions.refresh()
        if self.compare_active():  # the Compare view has its own buttons: no pane to act on
            for key in COMPARE_GREYED:
                self._actions.action(key).setEnabled(False)
        self._send_button.setEnabled(self._actions.action("send").isEnabled())
        self._receive_button.setEnabled(self._actions.action("receive").isEnabled())
        self._actions.action("show_hidden").setChecked(self._settings.show_hidden)
        self._compare_view.set_busy(self._busy)
        self._compare_view.set_verify_available(self._capabilities.crc)
        self._next_pane.setEnabled(not self._busy)  # the serial link is busy: no queued listings

    # -- observation points for tests
    def operation_running(self) -> bool:
        return self._busy

    def dot_notice(self) -> str:
        return self._dot_notice.text()

    def dot_version_known(self) -> bool:
        return self._version_known

    def compare_verify_enabled(self) -> bool:
        return self._compare_view.verify_enabled()

    def menu_titles(self) -> list[str]:
        return [action.text() for action in self.menuBar().actions()]

    def _menu(self, title: str) -> QMenu:
        return next(a.menu() for a in self.menuBar().actions() if a.text() == title)

    @staticmethod
    def _entries(menu: QMenu) -> list[tuple[str, str, bool]]:
        return [
            (a.text(), a.shortcut().toString(QKeySequence.PortableText), a.isEnabled())
            for a in menu.actions()
            if not a.isSeparator()
        ]

    def menu_entries(self, title: str) -> list[tuple[str, str, bool]]:
        """(label, shortcut, enabled) of each entry of a menu."""
        return self._entries(self._menu(title))

    def _find(self, menu: QMenu, path: str):
        first, _, rest = path.partition("/")
        found = next(a for a in menu.actions() if a.text() == first)
        return self._find(found.menu(), rest) if rest else found

    def trigger_menu(self, title: str, entry: str) -> None:
        """Click an entry (`Sort by/Name` for one in a submenu); a greyed entry does nothing."""
        self._find(self._menu(title), entry).trigger()

    def entry_enabled(self, title: str, entry: str) -> bool:
        return self._find(self._menu(title), entry).isEnabled()

    def entry_checked(self, title: str, entry: str) -> bool:
        return self._find(self._menu(title), entry).isChecked()

    def context_entries(self, side: str, row: str | None) -> list[tuple[str, str, bool]]:
        return self._entries(self.context_menu(side, row))

    def trigger_context(self, side: str, row: str | None, entry: str) -> None:
        self._find(self.context_menu(side, row), entry).trigger()

    def summary_text(self) -> str:
        return self._summary.text()

    def next_pane_state(self) -> str:
        return self._state

    def next_pane_text(self) -> str:
        return self.waiting_card_text() if self._state == "waiting" else self.connection_text()

    def waiting_card_text(self) -> str:
        return "\n".join(label.text() for label in self._card_labels)

    def click_copy_command(self) -> None:
        self._copy_button.click()

    def connection_text(self) -> str:
        return self._connection.text()

    def selection_summary(self) -> str:
        return self._selection.text()

    def status_bar_shows_dot_notice(self) -> bool:
        return self._dot_notice.isVisibleTo(self) and self.statusBar().isAncestorOf(self._dot_notice)

    def progress_visible(self) -> bool:
        return self._op_row.isVisibleTo(self) and self._cancel_button.isVisibleTo(self)

    def centre_button_enabled(self, which: str) -> bool:
        return (self._send_button if which == "send" else self._receive_button).isEnabled()

    def click_centre_button(self, which: str) -> None:
        (self._send_button if which == "send" else self._receive_button).click()

    def splitter_sizes(self) -> list[int]:
        """The widths of the two panes (the centre column is fixed)."""
        left, _, right = self._splitter.sizes()
        return [left, right]

    def set_splitter_sizes(self, sizes: list[int]) -> None:
        self._splitter.setSizes([sizes[0], self._centre.width() or self._centre.minimumWidth(), sizes[1]])

    def next_pane(self) -> NextPane:
        return self._next_pane

    def local_pane(self) -> LocalPane:
        return self._local_pane

    def cancel_text(self) -> str:
        return self._cancel_button.text()

    def cancel_enabled(self) -> bool:
        return self._cancel_button.isEnabled()

    def open_settings(self) -> None:
        changed = self._ask_settings(self._settings)
        if changed is not None:
            self.apply_settings(changed)
            self._write_settings()

    def apply_settings(self, new: Settings) -> None:
        """Take the choices that act at once; a new language shows at the next start."""
        theme_changed = new.theme != self._settings.theme
        self._settings = new
        if theme_changed:
            self.refresh_theme()
        self._local_pane.set_show_hidden(new.show_hidden)
        self._next_pane.set_show_hidden(new.show_hidden)
        self._update_actions()

    def _write_settings(self) -> None:
        if self._settings_path is None:
            return
        s = self._settings
        s.local_folder = self._local_pane.path() or s.local_folder
        s.next_folder = self._next_pane.path() or s.next_folder
        s.local_sort, s.next_sort = self._local_pane.sort(), self._next_pane.sort()
        sizes = self.splitter_sizes()
        if len(sizes) == 2 and all(n > 0 for n in sizes):
            s.splitter = tuple(sizes)
        s.geometry = base64.b64encode(bytes(self.saveGeometry())).decode()
        try:
            settings_store.save(s, self._settings_path)
        except OSError:
            pass  # the app still works; the choices are just not kept

    def closeEvent(self, event) -> None:
        self._write_settings()
        self._cancel.set()
        self._listener.end_session()  # the Next is told to quit before the link goes
        self._bridge.stop()
        self._local_pane.shutdown()
        self._next_pane.shutdown()
        super().closeEvent(event)

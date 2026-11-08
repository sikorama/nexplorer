from __future__ import annotations

import base64
import os
import threading
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtNetwork import QAbstractSocket, QNetworkInterface
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from nexplorer import settings as settings_store
from nexplorer.i18n import available_languages, set_language, tr
from nexplorer.protocol import Listener
from nexplorer.transfer import Result, copy, is_plain_name, make_folder, move, receive, remove, rename, send
from nexplorer.settings import Settings
from nexplorer.ui.bridge import ListenerBridge
from nexplorer.ui.panes import LocalPane, NextPane

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


def _ask_name_dialog(title: str, initial: str = "") -> str | None:
    text, accepted = QInputDialog.getText(None, title, tr("Name"), text=initial)
    return text if accepted else None


def _confirm_delete_dialog(message: str) -> bool:
    answer = QMessageBox.warning(
        None, tr("Delete"), message, QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel
    )
    return answer == QMessageBox.Yes


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
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    form = QFormLayout(dialog)
    form.addRow(hidden)
    form.addRow(crc)
    form.addRow(tr("Language"), language)
    form.addRow(buttons)
    if dialog.exec() != QDialog.Accepted:
        return None
    return Settings(
        **{
            **current.__dict__,
            "show_hidden": hidden.isChecked(),
            "crc_after_upload": crc.isChecked(),
            "language": language.currentText(),
        }
    )


class _Operation(QObject):
    progress = Signal(str, int)
    finished = Signal(object)  # transfer.Result, or the exception that ended it
    disconnected = Signal()  # the Next was told to leave (or the wait ran out)


class MainWindow(QMainWindow):
    def __init__(
        self,
        listener: Listener,
        local_addresses: Callable[[], list[tuple[str, str]]] = local_ipv4_addresses,
        ask_name: Callable[[str, str], str | None] = _ask_name_dialog,
        confirm_delete: Callable[[str], bool] = _confirm_delete_dialog,
        settings_path: Path | None = None,
        ask_settings: Callable[[Settings], Settings | None] = _settings_dialog,
    ):
        super().__init__()
        # Without a path nothing is read or written (tests, throwaway windows).
        self._settings_path = settings_path
        self._settings = settings_store.load(settings_path) if settings_path else Settings()
        self._ask_settings = ask_settings
        self._ask_name, self._confirm_delete = ask_name, confirm_delete
        self.setWindowTitle("nexplorer")
        self._local_addresses = local_addresses

        self._waiting = QLabel()
        self._waiting.setTextFormat(Qt.PlainText)
        self._waiting.setAlignment(Qt.AlignCenter)
        self._waiting.setWordWrap(True)
        self._connected = QLabel()
        self._next_pane = NextPane()
        self._connected_page = QWidget()
        page = QVBoxLayout(self._connected_page)
        page.addWidget(self._connected)
        page.addWidget(self._next_pane, 1)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._waiting)
        self._stack.addWidget(self._connected_page)

        root = QWidget()
        start = self._settings.local_folder
        self._local_pane = LocalPane(start if os.path.isdir(start) else os.path.expanduser("~"))
        self._next_pane.preferred_path = self._settings.next_folder
        self._local_pane.set_sort(self._settings.local_sort)
        self._next_pane.set_sort(self._settings.next_sort)
        self._local_pane.set_show_hidden(self._settings.show_hidden)
        self._next_pane.set_show_hidden(self._settings.show_hidden)
        row = QHBoxLayout()
        row.addWidget(self._pane(tr("Local"), self._local_pane))
        row.addWidget(self._pane(tr("Next"), self._stack))

        self._send = QPushButton(tr("Send \u2192"))
        self._send.clicked.connect(self.send_selected)
        self._receive = QPushButton(tr("\u2190 Receive"))
        self._receive.clicked.connect(self.receive_selected)
        self._new_folder = QPushButton(tr("New folder on Next"))
        self._new_folder.clicked.connect(self.new_folder)
        self._rename = QPushButton(tr("Rename on Next"))
        self._rename.clicked.connect(self.rename_selected)
        self._copy = QPushButton(tr("Copy on Next"))
        self._copy.clicked.connect(self.copy_selected)
        self._cut = QPushButton(tr("Cut on Next"))
        self._cut.clicked.connect(self.cut_selected)
        self._paste = QPushButton(tr("Paste on Next"))
        self._paste.clicked.connect(self.paste)
        self._delete = QPushButton(tr("Delete on Next"))
        self._delete.clicked.connect(self.delete_selected)
        actions = QHBoxLayout()
        actions.addWidget(self._send)
        actions.addWidget(self._receive)
        actions.addWidget(self._new_folder)
        actions.addWidget(self._rename)
        actions.addWidget(self._copy)
        actions.addWidget(self._cut)
        actions.addWidget(self._paste)
        actions.addWidget(self._delete)
        actions.addStretch(1)
        self._settings_button = QPushButton(tr("Settings"))
        self._settings_button.clicked.connect(self.open_settings)
        actions.addWidget(self._settings_button)
        self._disconnect = QPushButton(tr("Disconnect"))
        self._disconnect.clicked.connect(self.disconnect)
        actions.addWidget(self._disconnect)
        self._quit_button = QPushButton(tr("Quit"))
        self._quit_button.setShortcut("Ctrl+Q")
        self._quit_button.clicked.connect(self.close)
        actions.addWidget(self._quit_button)

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
        self._op_row.hide()
        self._busy = False
        self._cancel = threading.Event()
        self._operation = _Operation()
        self._operation.progress.connect(self._on_progress)
        self._operation.finished.connect(self._on_finished)
        self._disconnecting = False
        self._clipboard: tuple[str, str, list] | None = None  # ("copy" or "cut", Next folder, entries)
        self._clear_clipboard_if_clean = False
        self._operation.disconnected.connect(self._on_disconnected)
        self._next_pane.selection_changed.connect(self._update_actions)

        column = QVBoxLayout(root)
        column.addLayout(actions)
        column.addLayout(row, 1)
        column.addWidget(self._summary)
        column.addWidget(self._op_row)
        self.setCentralWidget(root)
        self.resize(900, 500)
        if self._settings.geometry:
            self.restoreGeometry(base64.b64decode(self._settings.geometry))

        self._show_waiting()
        self._listener = listener
        self._bridge = ListenerBridge(listener)
        self._bridge.session_started.connect(self._show_connected)

        self._next_pane.files_dropped.connect(self.drop_files)
        self._local_pane.next_entries_dropped.connect(lambda names, _row: self.drop_next_entries(names))
        self._next_pane.entries_moved.connect(self.move_dropped)
        self._next_pane.copy_requested.connect(self.copy_selected)
        self._next_pane.cut_requested.connect(self.cut_selected)
        self._next_pane.paste_requested.connect(self.paste)
        self._bridge.session_ready.connect(self._next_pane.bind)
        self._bridge.session_ready.connect(lambda _s: self._update_actions())
        self._bridge.session_ended.connect(self._show_waiting)

    @staticmethod
    def _pane(title: str, body: QWidget) -> QWidget:
        box = QWidget()
        col = QVBoxLayout(box)
        head = QLabel(title)
        head.setStyleSheet("font-weight: bold")
        col.addWidget(head)
        col.addWidget(body, 1)
        return box

    def _show_waiting(self) -> None:
        self._clipboard = None
        self._next_pane.unbind()
        lines = [tr("Waiting for a Next"), ""]
        for name, ip in self._local_addresses():
            lines.append(f"{name}: {ip}")
        lines += [
            "",
            tr("On the Next, run:"),
            SYNC_COMMAND,
            "",
            tr("The Local address must match the one in") + f" {CONFIG_FILE}",
        ]
        self._waiting.setText("\n".join(lines))
        self._stack.setCurrentWidget(self._waiting)
        self._update_actions()

    def _show_connected(self, address: str) -> None:
        self._connected.setText(
            f'<span style="color:#2ecc40">\u25cf</span> {tr("Connected")} \u2014 {address}'
        )
        self._stack.setCurrentWidget(self._connected_page)

    # -- send and receive
    def send_selected(self) -> None:
        """Send the selected Local entries to the Next folder shown."""
        session = self._next_pane.session()
        paths = [os.path.join(self._local_pane.path(), e.name) for e in self._local_pane.selected_entries()]
        folder = self._next_pane.path()
        verify = self._settings.crc_after_upload
        if session and paths and folder:
            self._run(lambda progress, cancel: send(session, paths, folder, progress, cancel, verify_crc=verify))

    def drop_files(self, paths: list[str], subfolder: str = "") -> None:
        """Files dropped on the Next pane: send them into the folder shown, or the subfolder hit."""
        session, folder = self._next_pane.session(), self._next_pane.folder_path(subfolder)
        verify = self._settings.crc_after_upload
        if session and paths and folder:
            self._run(lambda progress, cancel: send(session, paths, folder, progress, cancel, verify_crc=verify))

    def drop_next_entries(self, names: list[str]) -> None:
        """Next entries dragged onto the Local pane: receive them into the Local folder shown."""
        session = self._next_pane.session()
        wanted = set(names)
        entries = [e for e in self._next_pane.entries() if e.name in wanted]
        source, target = self._next_pane.path(), self._local_pane.path()
        if session and entries and source and target:
            self._run(lambda progress, cancel: receive(session, source, entries, target, progress, cancel))

    def receive_selected(self) -> None:
        """Receive the selected Next entries into the Local folder shown."""
        session = self._next_pane.session()
        entries = self._next_pane.selected_entries()
        source, target = self._next_pane.path(), self._local_pane.path()
        if session and entries and source and target:
            self._run(lambda progress, cancel: receive(session, source, entries, target, progress, cancel))

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
        if self._next_pane.session() is not None and entries:
            self._clipboard = (mode, self._next_pane.path(), entries)
            self._update_actions()

    def paste(self) -> None:
        """Copy or move the marked entries into the Next folder shown."""
        session, target = self._next_pane.session(), self._next_pane.path()
        if not session or not target or self._clipboard is None or self._busy:
            return
        mode, source, entries = self._clipboard
        action = move if mode == "cut" else copy
        self._clear_clipboard_if_clean = mode == "cut"  # a failed move can be retried
        self._run(lambda progress, cancel: action(session, source, entries, target, progress, cancel))

    def move_dropped(self, names: list[str], row: str) -> None:
        """Next entries dropped on a folder row of the Next pane: move them into that folder."""
        session, source = self._next_pane.session(), self._next_pane.path()
        target = self._next_pane.folder_path(row) if row else ""
        wanted = set(names)
        entries = [e for e in self._next_pane.entries() if e.name in wanted]
        if session and source and target and target != source and entries:
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
            f"{tr('Delete')} {len(entries)} {tr('items')} {tr('from the Next')}, {tr('starting with')} \u00ab{entries[0].name}\u00bb?\n"
            + tr("The Next has no recycle bin.")
        )
        if self._confirm_delete(message):
            self._run(lambda progress, cancel: remove(session, folder, entries, progress, cancel))

    def _run(self, work: Callable) -> None:
        """Run one modifying operation off the UI thread; only one at a time."""
        if self._busy:
            return
        self._busy = True
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
        self._next_pane.reload()
        self._local_pane.reload()
        self._update_actions()

    def _update_actions(self) -> None:
        """Modifying actions follow the Session and are greyed while one operation runs."""
        connected = self._next_pane.session() is not None
        enabled = connected and not self._busy
        selected = len(self._next_pane.selected_names())
        self._send.setEnabled(enabled)
        self._receive.setEnabled(enabled)
        self._new_folder.setEnabled(enabled)
        self._rename.setEnabled(enabled and selected == 1)
        self._delete.setEnabled(enabled and selected >= 1)
        self._copy.setEnabled(enabled and selected >= 1)
        self._cut.setEnabled(enabled and selected >= 1)
        self._paste.setEnabled(enabled and self._clipboard is not None)
        self._disconnect.setEnabled(connected and not self._disconnecting)
        self._next_pane.setEnabled(not self._busy)  # the serial link is busy: no queued listings

    # -- observation points for tests
    def operation_running(self) -> bool:
        return self._busy

    def delete_enabled(self) -> bool:
        return self._delete.isEnabled()

    def rename_enabled(self) -> bool:
        return self._rename.isEnabled()

    def new_folder_enabled(self) -> bool:
        return self._new_folder.isEnabled()

    def disconnect_enabled(self) -> bool:
        return self._disconnect.isEnabled()

    def copy_enabled(self) -> bool:
        return self._copy.isEnabled()

    def cut_enabled(self) -> bool:
        return self._cut.isEnabled()

    def paste_enabled(self) -> bool:
        return self._paste.isEnabled()

    def delete_text(self) -> str:
        return self._delete.text()

    def rename_text(self) -> str:
        return self._rename.text()

    def new_folder_text(self) -> str:
        return self._new_folder.text()

    def actions_enabled(self) -> bool:
        return self._send.isEnabled() and self._receive.isEnabled()

    def summary_text(self) -> str:
        return self._summary.text()

    def next_pane_state(self) -> str:
        return "waiting" if self._stack.currentWidget() is self._waiting else "connected"

    def next_pane_text(self) -> str:
        widget = self._waiting if self.next_pane_state() == "waiting" else self._connected
        return widget.text()

    def next_pane(self) -> NextPane:
        return self._next_pane

    def local_pane(self) -> LocalPane:
        return self._local_pane

    def cancel_text(self) -> str:
        return self._cancel_button.text()

    def cancel_enabled(self) -> bool:
        return self._cancel_button.isEnabled()

    def quit_text(self) -> str:
        return self._quit_button.text()

    def open_settings(self) -> None:
        changed = self._ask_settings(self._settings)
        if changed is not None:
            self.apply_settings(changed)
            self._write_settings()

    def apply_settings(self, new: Settings) -> None:
        """Take the choices that act at once; a new language shows at the next start."""
        self._settings = new
        self._local_pane.set_show_hidden(new.show_hidden)
        self._next_pane.set_show_hidden(new.show_hidden)

    def _write_settings(self) -> None:
        if self._settings_path is None:
            return
        s = self._settings
        s.local_folder = self._local_pane.path() or s.local_folder
        s.next_folder = self._next_pane.path() or s.next_folder
        s.local_sort, s.next_sort = self._local_pane.sort(), self._next_pane.sort()
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

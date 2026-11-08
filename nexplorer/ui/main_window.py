from __future__ import annotations

import os
import threading
from typing import Callable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtNetwork import QAbstractSocket, QNetworkInterface
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from nexplorer.i18n import tr
from nexplorer.protocol import Listener
from nexplorer.transfer import Result, receive, send
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


class _Operation(QObject):
    progress = Signal(str, int)
    finished = Signal(object)  # transfer.Result, or the exception that ended it


class MainWindow(QMainWindow):
    def __init__(
        self,
        listener: Listener,
        local_addresses: Callable[[], list[tuple[str, str]]] = local_ipv4_addresses,
    ):
        super().__init__()
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
        self._local_pane = LocalPane(os.path.expanduser("~"))
        row = QHBoxLayout()
        row.addWidget(self._pane(tr("Local"), self._local_pane))
        row.addWidget(self._pane(tr("Next"), self._stack))

        self._send = QPushButton(tr("Send \u2192"))
        self._send.clicked.connect(self.send_selected)
        self._receive = QPushButton(tr("\u2190 Receive"))
        self._receive.clicked.connect(self.receive_selected)
        actions = QHBoxLayout()
        actions.addWidget(self._send)
        actions.addWidget(self._receive)
        actions.addStretch(1)
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

        column = QVBoxLayout(root)
        column.addLayout(actions)
        column.addLayout(row, 1)
        column.addWidget(self._summary)
        column.addWidget(self._op_row)
        self.setCentralWidget(root)
        self.resize(900, 500)

        self._show_waiting()
        self._listener = listener
        self._bridge = ListenerBridge(listener)
        self._bridge.session_started.connect(self._show_connected)

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
        if session and paths and folder:
            self._run(lambda progress, cancel: send(session, paths, folder, progress, cancel))

    def receive_selected(self) -> None:
        """Receive the selected Next entries into the Local folder shown."""
        session = self._next_pane.session()
        entries = self._next_pane.selected_entries()
        source, target = self._next_pane.path(), self._local_pane.path()
        if session and entries and source:
            self._run(lambda progress, cancel: receive(session, source, entries, target, progress, cancel))

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
        if isinstance(outcome, Result):
            lines = [f"{f.name}: {f.reason}" for f in outcome.failures]
            head = tr("Cancelled") if outcome.cancelled else tr("Done")
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
        enabled = self._next_pane.session() is not None and not self._busy
        self._send.setEnabled(enabled)
        self._receive.setEnabled(enabled)
        self._next_pane.setEnabled(not self._busy)  # the serial link is busy: no queued listings

    # -- observation points for tests
    def operation_running(self) -> bool:
        return self._busy

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

    def closeEvent(self, event) -> None:
        self._cancel.set()
        self._listener.end_session()  # the Next is told to quit before the link goes
        self._bridge.stop()
        self._local_pane.shutdown()
        self._next_pane.shutdown()
        super().closeEvent(event)

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtNetwork import QAbstractSocket, QNetworkInterface
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from nexplorer.i18n import tr
from nexplorer.protocol import Listener
from nexplorer.ui.bridge import ListenerBridge

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
        self._connected.setAlignment(Qt.AlignCenter)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._waiting)
        self._stack.addWidget(self._connected)

        root = QWidget()
        row = QHBoxLayout(root)
        row.addWidget(self._pane(tr("Local"), QLabel()))
        row.addWidget(self._pane(tr("Next"), self._stack))
        self.setCentralWidget(root)
        self.resize(900, 500)

        self._show_waiting()
        self._bridge = ListenerBridge(listener)
        self._bridge.session_started.connect(self._show_connected)
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

    def _show_connected(self, address: str) -> None:
        self._connected.setText(
            f'<span style="color:#2ecc40">\u25cf</span> {tr("Connected")} \u2014 {address}'
        )
        self._stack.setCurrentWidget(self._connected)

    # -- observation points for tests
    def next_pane_state(self) -> str:
        return "waiting" if self._stack.currentWidget() is self._waiting else "connected"

    def next_pane_text(self) -> str:
        return self._stack.currentWidget().text()

    def closeEvent(self, event) -> None:
        self._bridge.stop()
        super().closeEvent(event)

"""Thin off-thread layer: watches the Listener and reports Session life by signals."""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from nexplorer.protocol import Listener


class ListenerBridge(QObject):
    session_started = Signal(str)  # Next's address
    dot_version = Signal(str)
    session_ended = Signal()

    def __init__(self, listener: Listener):
        super().__init__()
        self._listener = listener
        self._stop = False
        threading.Thread(target=self._watch, daemon=True).start()

    def stop(self) -> None:
        self._stop = True

    def _watch(self) -> None:
        while not self._stop:
            session = self._listener.wait_session(timeout=0.2)
            if session is None:
                continue
            self._emit(self.session_started, session.peer_address)
            try:
                version = session.dot_version(timeout=30)
            except (ConnectionError, TimeoutError):
                version = None
            if version is not None:
                self._emit(self.dot_version, version)
            while not self._stop and not session.wait_closed(timeout=0.2):
                pass
            self._emit(self.session_ended)

    def _emit(self, signal, *args) -> None:
        if self._stop:
            return
        try:
            signal.emit(*args)
        except RuntimeError:  # the window is already gone
            self._stop = True

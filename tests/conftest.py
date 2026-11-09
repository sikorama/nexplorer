import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
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


def dispose(app, *widgets):
    """Tear Qt widgets down in order: stop their threads' reports, then delete them."""
    for w in widgets:
        if hasattr(w, "shutdown"):
            w.shutdown()
    time.sleep(0.05)
    app.processEvents()
    for w in widgets:
        w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()

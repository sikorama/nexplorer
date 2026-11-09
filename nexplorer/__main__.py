import signal
import sys
from collections.abc import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from nexplorer import settings
from nexplorer.i18n import set_language, tr
from nexplorer.protocol import Listener
from nexplorer.ui.main_window import MainWindow

PORT = 2048


def close_on_signals(app: QApplication, window: MainWindow) -> QTimer:
    """Ctrl-C and `kill` close the window like the Quit button, so the Next is told
    to quit. The timer lets Python see the signal while Qt's loop runs."""
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: window.close())
    timer = QTimer(app)
    timer.start(200)
    timer.timeout.connect(lambda: None)
    return timer


def _error_dialog(message: str) -> None:
    QMessageBox.critical(None, "nexplorer", message)


def main(show_error: Callable[[str], None] = _error_dialog) -> int:
    path = settings.config_path()
    set_language(settings.load(path).language)
    app = QApplication.instance() or QApplication(sys.argv)
    listener = Listener(port=PORT)
    try:
        listener.start()
    except OSError as e:
        listener.stop()  # closes the socket opened before the failed bind
        message = f"{tr('Cannot listen on port')} {PORT}: {e}"
        print(message, file=sys.stderr)
        show_error(message)  # packaged builds have no console
        return 1
    window = MainWindow(listener, settings_path=path)
    window.show()
    keep_alive = close_on_signals(app, window)  # noqa: F841 - the timer must stay referenced
    code = app.exec()
    listener.stop()
    return code


if __name__ == "__main__":
    sys.exit(main())

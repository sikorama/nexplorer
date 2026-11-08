import sys

from PySide6.QtWidgets import QApplication

from nexplorer.i18n import set_language, tr
from nexplorer.protocol import Listener
from nexplorer.ui.main_window import MainWindow

PORT = 2048


def main() -> int:
    set_language("en")
    app = QApplication(sys.argv)
    listener = Listener(port=PORT)
    try:
        listener.start()
    except OSError as e:
        print(f"{tr('Cannot listen on port')} {PORT}: {e}", file=sys.stderr)
        return 1
    window = MainWindow(listener)
    window.show()
    code = app.exec()
    listener.stop()
    return code


if __name__ == "__main__":
    sys.exit(main())

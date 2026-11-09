"""The embedded icon set (a Lucide subset, see THIRD_PARTY_NOTICES.md) and what uses it.

Icons are SVG files drawn with `currentColor`; `icon(name, colour)` is the one way to get a
tinted icon, so a theme only has to pass its palette colour."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

from nexplorer.protocol import Entry

ICON_DIR = Path(__file__).parent / "svg"
_SIZE = 64  # rendered large, the views scale it down

# The icon of each shared action (menus, context menus, toolbar).
ACTION_ICONS = {
    "new_folder": "folder-plus",
    "rename": "pencil",
    "delete": "trash-2",
    "settings": "settings",
    "quit": "log-out",
    "copy": "copy",
    "cut": "scissors",
    "paste": "clipboard-paste",
    "select_all": "check-check",
    "send": "upload",
    "receive": "download",
    "compare": "git-compare",
    "disconnect": "unplug",
    "show_hidden": "eye",
    "refresh": "refresh-cw",
    "about": "info",
}
# The frequent actions, in toolbar order (None is a separator).
TOOLBAR_ACTIONS = (
    "new_folder", "rename", "delete", None,
    "copy", "cut", "paste", None,
    "send", "receive", "compare", None,
    "refresh",
)  # fmt: skip

FOLDER_ICON = "folder"
FILE_ICON = "file"
# Next rows by extension; anything else is a generic file.
NEXT_TYPE_ICONS = {
    "nex": "gamepad-2",
    "tap": "cassette-tape",
    "tzx": "cassette-tape",
    "sna": "camera",
    "z80": "camera",
    "szx": "camera",
    "bas": "file-code",
    "asm": "file-code",
    "txt": "file-text",
    "md": "file-text",
}


def available() -> set[str]:
    return {p.stem for p in ICON_DIR.glob("*.svg")}


def default_colour() -> QColor:
    """The text colour of the current palette: visible on the window background."""
    return QApplication.palette().color(QPalette.WindowText)


@lru_cache(maxsize=None)
def _render(name: str, rgba: str) -> QPixmap:
    svg = (ICON_DIR / f"{name}.svg").read_text(encoding="utf-8").replace("currentColor", rgba)
    pixmap = QPixmap(_SIZE, _SIZE)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    return pixmap


def icon(name: str, colour: QColor | str | None = None) -> QIcon:
    """The icon `name` drawn in `colour` (the palette text colour when omitted)."""
    colour = QColor(colour) if colour is not None else default_colour()
    return QIcon(_render(name, colour.name(QColor.HexRgb)))


def next_icon_name(entry: Entry) -> str:
    """The embedded icon of a row of the Next."""
    if entry.is_dir:
        return FOLDER_ICON
    extension = entry.name.rpartition(".")[2].lower() if "." in entry.name.strip(".") else ""
    return NEXT_TYPE_ICONS.get(extension, FILE_ICON)

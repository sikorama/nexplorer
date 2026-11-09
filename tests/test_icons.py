"""The embedded icon set: every name the interface uses exists, icons take any colour."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tomllib
from pathlib import Path

from PySide6.QtGui import QColor

from nexplorer.protocol import Entry
from nexplorer.ui import icons


def test_every_icon_name_used_by_the_interface_exists():
    used = set(icons.ACTION_ICONS.values())
    used |= set(icons.NEXT_TYPE_ICONS.values()) | {icons.FOLDER_ICON, icons.FILE_ICON}
    assert used <= icons.available()


def test_toolbar_actions_have_icons():
    keys = [k for k in icons.TOOLBAR_ACTIONS if k]
    assert keys and all(k in icons.ACTION_ICONS for k in keys)


def test_next_rows_get_icons_by_type():
    name = icons.next_icon_name
    assert name(Entry("GAMES", True, 0)) == "folder"
    assert name(Entry("readme", False, 1)) == "file"
    assert len({name(Entry(f"x.{e}", False, 1)) for e in ("nex", "tap", "sna", "bas")}) == 4
    assert name(Entry("GAME.NEX", False, 1)) == name(Entry("game.nex", False, 1))
    assert name(Entry(".nex", False, 1)) == "file"  # a hidden file, not an extension


def test_an_icon_is_drawn_in_the_requested_colour(app):
    def colours(colour):
        image = icons.icon("folder", colour).pixmap(24, 24).toImage()
        return {QColor(image.pixel(x, y)).name() for x in range(24) for y in range(24) if QColor.fromRgba(image.pixel(x, y)).alpha() == 255}

    assert colours("#ff0000") == {"#ff0000"}
    assert colours(QColor("#00ff00")) == {"#00ff00"}


def test_the_svg_files_are_packaged():
    root = Path(__file__).parent.parent
    data = tomllib.loads((root / "pyproject.toml").read_text())
    assert "nexplorer.ui" in data["tool"]["setuptools"]["packages"]
    assert "svg/*.svg" in data["tool"]["setuptools"]["package-data"]["nexplorer.ui"]

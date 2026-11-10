"""Where the sync-wrap.bas program shipped with nexplorer lives."""
from __future__ import annotations

import sys
from pathlib import Path

NAME = "sync-wrap.bas"
FOLDER = "sync-wrap"


def locate() -> Path | None:
    """The shipped program, or None when it cannot be found."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # PyInstaller's data folder
    else:
        base = Path(__file__).resolve().parent.parent
    path = base / FOLDER / NAME
    return path if path.is_file() else None

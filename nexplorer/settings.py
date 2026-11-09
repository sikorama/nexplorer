"""Settings: one JSON file in the user's configuration folder."""
from __future__ import annotations

import base64
import binascii
import json
import os
import sys
from dataclasses import dataclass, fields
from pathlib import Path

from nexplorer.i18n import available_languages

SORT_KEYS = ("name", "size", "type")


@dataclass
class Settings:
    local_folder: str = ""
    next_folder: str = ""
    geometry: str = ""  # base64 of QMainWindow.saveGeometry()
    language: str = "en"
    show_hidden: bool = False
    crc_after_upload: bool = False
    local_sort: tuple[str, bool] = ("name", False)
    next_sort: tuple[str, bool] = ("name", False)
    splitter: tuple[int, ...] = ()  # widths of the Local and ZX Spectrum Next panes; empty = even split


def config_path(
    platform: str = sys.platform, env: dict[str, str] | None = None, home: Path | None = None
) -> Path:
    env = os.environ if env is None else env
    home = home or Path.home()
    if platform == "win32":
        base = Path(env.get("APPDATA") or home / "AppData" / "Roaming")
    elif platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = Path(env.get("XDG_CONFIG_HOME") or home / ".config")
    return base / "nexplorer" / "settings.json"


def _valid(name: str, value: object) -> bool:
    if name.endswith("_sort"):
        return (
            isinstance(value, (list, tuple))
            and len(value) == 2
            and value[0] in SORT_KEYS
            and isinstance(value[1], bool)
        )
    if name == "splitter":
        return (
            isinstance(value, (list, tuple))
            and (len(value) == 0 or (len(value) == 2 and all(type(v) is int and v > 0 for v in value)))
        )
    if name == "geometry" and isinstance(value, str):
        try:
            base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            return False
    if name == "language":
        return isinstance(value, str) and value in available_languages()
    default = getattr(Settings, name)
    return isinstance(value, type(default))


def load(path: Path | None = None) -> Settings:
    try:
        data = json.loads((path or config_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Settings()
    if not isinstance(data, dict):
        return Settings()
    kept = {}
    for f in fields(Settings):
        if f.name in data and _valid(f.name, data[f.name]):
            kept[f.name] = tuple(data[f.name]) if f.name.endswith("_sort") or f.name == "splitter" else data[f.name]
    return Settings(**kept)


def save(settings: Settings, path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings.__dict__, indent=2), encoding="utf-8")

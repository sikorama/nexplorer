"""The places the Local drive selector offers: drive letters on Windows, Home, `/` and mounted media on Linux."""
from __future__ import annotations

import getpass
import os
import string
import sys
from pathlib import Path
from typing import Callable

Root = tuple[str, str]  # (label shown, folder path)


def _windows_drives() -> list[str]:
    return [f"{c}:\\" for c in string.ascii_uppercase if os.path.exists(f"{c}:\\")]


def _user() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - no user name: the per-user folders simply do not exist
        return ""


def local_roots(
    platform: str = sys.platform,
    *,
    home: Path | None = None,
    user: str | None = None,
    drives: Callable[[], list[str]] = _windows_drives,
    media_parents: list[str] | None = None,
    is_mount: Callable[[str], bool] = os.path.ismount,
) -> list[Root]:
    """The roots for `platform`. Read again each time the selector opens, so a card just plugged in shows.

    `drives` gives the Windows roots ("C:\\"); `media_parents` are the folders whose mount points are
    offered on Linux, and `is_mount` tells which of their children are mounted.
    """
    if platform == "win32":
        return [(d.rstrip("\\/"), d) for d in drives()]
    home = home or Path.home()
    roots: list[Root] = [("Home", str(home)), ("/", "/")]
    if media_parents is None:
        user = _user() if user is None else user
        media_parents = ["/media", f"/media/{user}", "/mnt", f"/run/media/{user}"]
    for parent in media_parents:
        try:
            children = sorted(os.scandir(parent), key=lambda e: e.name.lower())
        except OSError:
            continue
        for child in children:
            if child.is_dir() and is_mount(child.path) and all(child.path != r[1] for r in roots):
                roots.append((child.path, child.path))
    return roots

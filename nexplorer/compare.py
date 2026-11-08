"""Compare one Local folder with one Next folder (Qt-free).

Compare never deletes anything on either side: Apply only sends or receives."""
from __future__ import annotations

import fnmatch
import os
from collections import Counter
from dataclasses import dataclass
from typing import Callable

from nexplorer.protocol import Entry, Session
from nexplorer.transfer import Progress, Result, receive, send


# Rows shown to the user but never transferred.
BLOCKED = frozenset({"conflict", "invalid", "ignored", "hidden"})


@dataclass
class Row:
    name: str
    state: str  # "only-local", "only-next", "different", "identical" or a blocked state
    direction: str | None  # "to-next", "to-local" or None
    checked: bool
    local: Entry | None = None
    remote: Entry | None = None

    def reverse(self) -> None:
        """Flip the direction; a row without one starts as Local to Next."""
        self.direction = "to-local" if self.direction == "to-next" else "to-next"

    def transferable(self) -> bool:
        if self.state in BLOCKED:
            return False
        source = self.local if self.direction == "to-next" else self.remote
        return self.checked and self.direction is not None and source is not None


MAX_PATH_BYTES = 254
_FORBIDDEN = set('"*:<>?|\\/')


def _invalid(name: str, next_dir: str) -> bool:
    """A name or path the Next's file system refuses."""
    if any(c in _FORBIDDEN or ord(c) < 32 for c in name):
        return True
    return len(f"{next_dir}/{name}".encode("utf-8", "replace")) > MAX_PATH_BYTES


IGNORE_FILE = ".nexplorerignore"


def read_ignore(folder: str | os.PathLike) -> list[str]:
    """The glob patterns of the folder's .nexplorerignore, one per line, # for comments."""
    try:
        with open(os.path.join(folder, IGNORE_FILE), encoding="utf-8", errors="replace") as f:
            lines = [line.strip() for line in f]
    except OSError:
        return []
    return [line for line in lines if line and not line.startswith("#")]


def _blocked(name: str, next_dir: str, ignore: list[str], show_hidden: bool) -> str | None:
    if _invalid(name, next_dir):
        return "invalid"
    if any(fnmatch.fnmatchcase(name, p) for p in ignore):
        return "ignored"
    if not show_hidden and name.startswith("."):
        return "hidden"
    return None


def compare_level(
    local: list[Entry],
    remote: list[Entry],
    next_dir: str = "",
    ignore: list[str] = (),
    show_hidden: bool = True,
) -> list[Row]:
    """One row per name found on either side; sizes alone tell different from identical.

    Entries that must not move (invalid, conflicting, ignored, hidden) stay as rows in a
    blocked state, never dropped."""
    remote_by_name = {e.name.casefold(): e for e in remote}
    local_names = {e.name.casefold() for e in local}
    case_count = Counter(e.name.casefold() for e in local)
    rows = []
    for e in local:
        other = remote_by_name.get(e.name.casefold())
        blocked = _blocked(e.name, next_dir, ignore, show_hidden)
        if blocked != "invalid" and case_count[e.name.casefold()] > 1:
            blocked = "conflict"
        if blocked:
            rows.append(Row(e.name, blocked, None, False, e, other))
        elif other is None:
            rows.append(Row(e.name, "only-local", "to-next", True, e, None))
        elif other.size != e.size:
            rows.append(Row(e.name, "different", None, False, e, other))
        else:
            rows.append(Row(e.name, "identical", None, False, e, other))
    for e in remote:
        if e.name.casefold() in local_names:
            continue
        blocked = _blocked(e.name, next_dir, ignore, show_hidden)
        rows.append(Row(e.name, blocked or "only-next", None if blocked else "to-local", not blocked, None, e))
    return rows


def apply(
    session: Session,
    local_dir: str,
    next_dir: str,
    rows: list[Row],
    progress: Progress | None = None,
    cancel: Callable[[], bool] | None = None,
    verify_crc: bool = False,
) -> Result:
    """Transfer the checked rows one after the other, each in its own direction.

    Stops when the user cancels or the Session is lost."""
    total = Result()
    for r in rows:
        if not r.transferable():
            continue
        if cancel and cancel():
            total.cancelled = True
            break
        if r.direction == "to-next":
            one = send(session, [os.path.join(local_dir, r.name)], next_dir, progress, cancel, verify_crc=verify_crc)
        else:
            one = receive(session, next_dir, [r.remote], local_dir, progress, cancel)
        total.failures += one.failures
        if one.cancelled or one.dropped:
            total.cancelled, total.dropped = one.cancelled, one.dropped
            break
    return total

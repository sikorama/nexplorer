"""Compare one Local folder with one Next folder (Qt-free).

Compare never deletes anything on either side: Apply only sends or receives."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from nexplorer.protocol import Entry, Session
from nexplorer.transfer import Progress, Result, receive, send


@dataclass
class Row:
    name: str
    state: str  # "only-local", "only-next", "different" or "identical"
    direction: str | None  # "to-next", "to-local" or None
    checked: bool
    local: Entry | None = None
    remote: Entry | None = None

    def reverse(self) -> None:
        """Flip the direction; a row without one starts as Local to Next."""
        self.direction = "to-local" if self.direction == "to-next" else "to-next"

    def transferable(self) -> bool:
        source = self.local if self.direction == "to-next" else self.remote
        return self.checked and self.direction is not None and source is not None


def compare_level(local: list[Entry], remote: list[Entry]) -> list[Row]:
    """One row per name found on either side; sizes alone tell different from identical."""
    remote_by_name = {e.name: e for e in remote}
    local_names = {e.name for e in local}
    rows = []
    for e in local:
        other = remote_by_name.get(e.name)
        if other is None:
            rows.append(Row(e.name, "only-local", "to-next", True, e, None))
        elif other.size != e.size:
            rows.append(Row(e.name, "different", None, False, e, other))
        else:
            rows.append(Row(e.name, "identical", None, False, e, other))
    rows += [Row(e.name, "only-next", "to-local", True, None, e) for e in remote if e.name not in local_names]
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

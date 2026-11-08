"""Compare one Local folder with one Next folder (Qt-free).

Compare never deletes anything on either side: Apply only sends or receives."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from nexplorer.protocol import Entry, RemoteError, Session
from nexplorer.transfer import Failure, Progress, Result, receive, send


@dataclass
class Row:
    name: str
    state: str  # "only-local", "only-next", "different", "identical" or "not-scanned"
    direction: str | None  # "to-next", "to-local" or None
    checked: bool
    local: Entry | None = None
    remote: Entry | None = None
    children: list["Row"] | None = None  # the next level of a folder on both sides, once scanned

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
        elif e.is_dir and other.is_dir:
            rows.append(Row(e.name, "not-scanned", None, False, e, other))
        elif other.size != e.size:
            rows.append(Row(e.name, "different", None, False, e, other))
        else:
            rows.append(Row(e.name, "identical", None, False, e, other))
    rows += [Row(e.name, "only-next", "to-local", True, None, e) for e in remote if e.name not in local_names]
    return rows


def _join_next(folder: str, name: str) -> str:
    return folder.rstrip("/") + "/" + name


def _list_local(path: str, show_hidden: bool) -> list[Entry]:
    entries = []
    with os.scandir(path) as it:
        for e in it:
            if show_hidden or not e.name.startswith("."):
                is_dir = e.is_dir()
                entries.append(Entry(e.name, is_dir, 0 if is_dir else e.stat().st_size))
    return entries


def settle(row: Row) -> None:
    """A folder is identical only when everything below it was scanned and is identical."""
    if row.children is None:
        return
    for c in row.children:
        settle(c)
    states = {c.state for c in row.children}
    if "not-scanned" in states:
        row.state = "not-scanned"
    elif states <= {"identical"}:
        row.state = "identical"
    else:
        row.state = "different"


def expand(session: Session, row: Row, local_dir: str, next_dir: str, show_hidden: bool = True) -> None:
    """List the next level of a folder present on both sides (Local, then the Next)."""
    remote = [e for e in session.list_dir(_join_next(next_dir, row.name)) if show_hidden or not e.name.startswith(".")]
    row.children = compare_level(_list_local(os.path.join(local_dir, row.name), show_hidden), remote)
    settle(row)


def scan_all(
    session: Session,
    rows: list[Row],
    local_dir: str,
    next_dir: str,
    progress: Progress | None = None,
    cancel: Callable[[], bool] | None = None,
    show_hidden: bool = True,
) -> Result:
    """Expand every not scanned folder below `rows`; Cancel leaves the unreached ones not scanned."""
    result = Result()
    pending = [(r, local_dir, next_dir) for r in rows]
    done = 0
    while pending:
        r, ldir, ndir = pending.pop(0)
        if r.state == "not-scanned" and r.children is None:
            if cancel and cancel():
                result.cancelled = True
                break
            if progress:
                progress(r.name, 100 * done // (done + len(pending) + 1))
            try:
                expand(session, r, ldir, ndir, show_hidden)
            except (ConnectionError, TimeoutError):
                result.dropped = True
                result.failures.append(Failure(r.name, "session lost"))
                break
            except (OSError, RemoteError) as exc:
                result.failures.append(Failure(r.name, f"cannot list the folder: {exc}"))
                continue
            done += 1
        if r.children is not None:
            pending += [(c, os.path.join(ldir, r.name), _join_next(ndir, r.name)) for c in r.children]
    for r in rows:
        settle(r)
    return result


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
        if r.children is not None:
            sub = apply(
                session, os.path.join(local_dir, r.name), _join_next(next_dir, r.name),
                r.children, progress, cancel, verify_crc,
            )
            total.failures += sub.failures
            if sub.cancelled or sub.dropped:
                total.cancelled, total.dropped = sub.cancelled, sub.dropped
                break
            continue
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

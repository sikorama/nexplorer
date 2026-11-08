"""Compare one Local folder with one Next folder (Qt-free).

Compare never deletes anything on either side: Apply only sends or receives."""
from __future__ import annotations

import os
import zlib
from dataclasses import dataclass
from typing import Callable

from nexplorer.protocol import Entry, RemoteError, Session, Unanswered
from nexplorer.transfer import Failure, Progress, Result, receive, send


@dataclass
class Row:
    name: str
    state: str  # "only-local", "only-next", "different", "unverified" or "identical"
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
    """One row per name found on either side; a size mismatch is different, the same size stays unverified until Verify."""
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
            rows.append(Row(e.name, "unverified", None, False, e, other))
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


def verify(
    session: Session,
    local_dir: str,
    next_dir: str,
    rows: list[Row],
    cancel: Callable[[], bool] | None = None,
    timeout: float = 60,
) -> Result:
    """Settle the unverified rows: the Next's CRC-32 against the Local CRC, one file at a time.

    Only same-size files are asked (they are the unverified rows). A file whose CRC cannot
    be read stays unverified; a lost Session stops the run."""
    total = Result()
    for r in rows:
        if r.state != "unverified" or r.remote is None or r.remote.is_dir:
            continue
        if cancel and cancel():
            total.cancelled = True
            break
        target = next_dir.rstrip("/") + "/" + r.name
        try:
            expected = 0
            with open(os.path.join(local_dir, r.name), "rb") as f:
                while chunk := f.read(65536):
                    expected = zlib.crc32(chunk, expected)
            found = session.crc(target, timeout=timeout + r.remote.size / 15_000)
        except (RemoteError, OSError) as exc:
            total.failures.append(Failure(target, f"CRC not checked: {exc}"))
            if isinstance(exc, (TimeoutError, ConnectionError, Unanswered)):
                total.dropped = True
                break
            continue
        r.state = "identical" if found == expected else "different"
    return total

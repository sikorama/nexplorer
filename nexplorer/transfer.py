"""Send Local entries to the Next, receive Next entries into Local and delete Next entries (Qt-free).

Nothing here ever deletes anything on Local. `progress(name, percent)` and
`cancel()` are called from the thread that runs the transfer or from the
Session's thread: callers hand results to their own thread themselves."""
from __future__ import annotations

import os
import zlib
from dataclasses import dataclass, field
from typing import Callable

from nexplorer.protocol import Cancelled, Entry, RemoteError, Session, Unanswered

Progress = Callable[[str, int], None]


@dataclass
class Failure:
    name: str
    reason: str


@dataclass
class Result:
    failures: list[Failure] = field(default_factory=list)
    cancelled: bool = False
    dropped: bool = False  # the Session died: the operation stopped, the rest was left as it was


class _Stop(Exception):
    """The user cancelled: unwind out of the walk."""


class _Job:
    def __init__(
        self,
        session: Session,
        progress: Progress | None,
        cancel,
        timeout: float,
        total: int,
        verify_crc: bool = False,
    ):
        self.session, self.timeout, self.verify_crc = session, timeout, verify_crc
        self.result = Result()
        self._progress, self._cancel = progress, cancel
        self._total, self._done = total, 0

    def check_cancel(self) -> None:
        if self._cancel and self._cancel():
            self.result.cancelled = True
            raise _Stop

    def report(self, name: str, in_file: int = 0) -> None:
        if self._progress:
            percent = 100 if self._total == 0 else (self._done + in_file) * 100 // self._total
            self._progress(name, min(percent, 100))

    def set_total(self, total: int) -> None:
        self._total = total

    def finished(self, size: int) -> None:
        self._done += size

    def lose(self, name: str, reason: str) -> None:
        """The Session died: record the file it died on and stop the whole operation."""
        self.result.dropped = True
        self.result.cancelled = bool(self._cancel and self._cancel())  # a Cancel asked meanwhile still counts
        self.fail(name, f"session lost; {reason}")
        raise _Stop

    def fail(self, name: str, reason: str) -> None:
        self.result.failures.append(Failure(name, reason))


# -- send
def send(
    session: Session,
    local_paths: list[str],
    next_dir: str,
    progress: Progress | None = None,
    cancel: Callable[[], bool] | None = None,
    timeout: float = 60,
    verify_crc: bool = False,
) -> Result:
    """Upload files and folders (recursively) into `next_dir` on the Next.

    Sizes are always checked; `verify_crc` adds a CRC-32 check of each file (slow: the Next
    reads every file back, about 30 s per MB)."""
    job = _Job(session, progress, cancel, timeout, sum(_local_size(p) for p in local_paths), verify_crc)
    try:
        _send_entries(job, next_dir, local_paths, ())
    except _Stop:
        pass
    return job.result


def _send_entries(job: _Job, folder: str, paths: list[str], ancestors: tuple[str, ...]) -> None:
    """Send the files, then the sub-folders, of one Next folder."""
    files, folders = _split(job, folder, paths, ancestors)
    _upload_files(job, folder, files)
    for path in folders:
        _send_folder(job, path, _join(folder, _base(path)), ancestors)


def _split(job: _Job, folder: str, paths: list[str], ancestors: tuple[str, ...]) -> tuple[list[str], list[str]]:
    """Separate files from folders, failing what cannot go: a symlink back into a
    folder being walked, or a name the Next (ignoring case) would give to an earlier entry."""
    taken: dict[str, str] = {}  # lower-case name -> the Local name that took it
    files, folders = [], []
    ordered = [p for p in paths if not os.path.isdir(p)] + [p for p in paths if os.path.isdir(p)]
    for path in ordered:
        name, is_dir = _base(path), os.path.isdir(path)
        if name.lower() in taken:
            job.fail(
                _join(folder, name),
                f"same name as {taken[name.lower()]} on the Next (names ignore case): not sent",
            )
        elif is_dir and os.path.realpath(path) in ancestors:
            job.fail(_join(folder, name), "symlink loop: not sent")
        else:
            taken[name.lower()] = name
            (folders if is_dir else files).append(path)
    return files, folders


def _send_folder(job: _Job, local: str, target: str, ancestors: tuple[str, ...]) -> None:
    job.check_cancel()
    try:
        names = sorted(os.listdir(local))
    except OSError as exc:
        job.fail(target, f"cannot read the folder: {exc}")
        return
    try:
        job.session.make_dir(target, timeout=job.timeout)
    except ConnectionError:
        job.lose(target, "folder not created")
    except RemoteError as exc:
        try:  # esxDOS answers the same for "exists" and for real failures
            job.session.list_dir(target, timeout=job.timeout)
        except (RemoteError, OSError):
            job.fail(target, f"cannot create the folder: {exc}")
            return
    except OSError as exc:  # the Session died or timed out
        job.fail(target, f"cannot create the folder: {exc}")
        return
    _send_entries(job, target, [os.path.join(local, n) for n in names], ancestors + (os.path.realpath(local),))


def _upload_files(job: _Job, folder: str, files: list[str]) -> None:
    """Put the files into one Next folder, then check their sizes with one listing."""
    sent: dict[str, tuple[str, int]] = {}  # lower-case name -> (name, expected size)
    try:
        for local in files:
            job.check_cancel()
            name = _base(local)
            reached = [0]  # bytes handed to the Next so far for this file

            def on_progress(n: int, name: str = name, reached: list[int] = reached) -> None:
                reached[0] = n
                job.report(name, n)

            try:
                size = os.path.getsize(local)
                job.report(name)
                job.session.put_file(
                    local,
                    _join(folder, name),
                    timeout=job.timeout,
                    progress=on_progress,
                    cancel=job._cancel,
                )
                sent[name.lower()] = (name, size, local)
                job.finished(size)
                job.report(name)
            except Cancelled:
                job.result.cancelled = True
                job.fail(_join(folder, name), _partial_reason("cancelled", job, folder, name))
                raise _Stop from None
            except (ConnectionError, TimeoutError):  # a put cut short ends the Session
                reason = (
                    f"{reached[0]} bytes had been sent, a partial file may be left"
                    if reached[0]
                    else "file not sent"
                )
                job.lose(_join(folder, name), reason)
            except (RemoteError, OSError) as exc:
                job.fail(_join(folder, name), _partial_reason(str(exc), job, folder, name))
    finally:
        _check_sizes(job, folder, sent)


def _check_crc(job: _Job, folder: str, name: str, size: int, local: str) -> str:
    """Compare the CRC-32s. Returns why the checks should stop (no reply, link lost), or ""."""
    target = _join(folder, name)
    try:
        expected = 0
        with open(local, "rb") as f:
            while chunk := f.read(65536):
                expected = zlib.crc32(chunk, expected)
        found = job.session.crc(target, timeout=job.timeout + size / 15_000)
    except (RemoteError, OSError) as exc:
        job.fail(target, f"CRC not checked: {exc}")
        return str(exc) if isinstance(exc, (TimeoutError, ConnectionError, Unanswered)) else ""
    if found != expected:
        job.fail(target, f"CRC on the Next is {found:08X}, expected {expected:08X}")
    return ""


def _check_sizes(job: _Job, folder: str, sent: dict[str, tuple[str, int, str]]) -> None:
    if not sent:
        return
    try:
        found = {e.name.lower(): e.size for e in job.session.list_dir(folder, timeout=job.timeout)}
    except (RemoteError, OSError) as exc:  # a dead Session or a timeout too
        for name, _, _ in sent.values():
            job.fail(_join(folder, name), f"size not checked: {exc}")
        return
    crc_stopped = ""  # why the CRC checks ended early: the dot is not answering
    for key, (name, expected, local) in sent.items():
        if found.get(key) != expected:
            job.fail(
                _join(folder, name),
                f"size on the Next is {found.get(key, 'missing')}, expected {expected}",
            )
        elif job.verify_crc and not job.result.cancelled:
            job.check_cancel()
            if crc_stopped:
                job.fail(_join(folder, name), f"CRC not checked: {crc_stopped}")
            else:
                crc_stopped = _check_crc(job, folder, name, expected, local)


def _partial_reason(reason: str, job: _Job, folder: str, name: str) -> str:
    """The failure reason, with the size of the partial file the Next may keep."""
    try:
        for entry in job.session.list_dir(folder, timeout=job.timeout):
            if entry.name.lower() == name.lower():
                return f"{reason}; partial file of {entry.size} bytes left"
    except (RemoteError, ConnectionError, TimeoutError):
        pass
    return reason


# -- receive
def receive(
    session: Session,
    next_dir: str,
    entries: list[Entry],
    local_dir: str,
    progress: Progress | None = None,
    cancel: Callable[[], bool] | None = None,
    timeout: float = 60,
) -> Result:
    """Download Next entries (folders recursively) from `next_dir` into `local_dir`.

    Cancel is honoured between files: the dot cannot be told to stop a get."""
    job = _Job(session, progress, cancel, timeout, 0)
    try:
        nodes = _scan(job, next_dir, entries)  # one listing per folder, so the total is known
        job.set_total(sum(_file_bytes(n) for n in nodes))
        _download(job, next_dir, nodes, local_dir)
    except _Stop:
        pass
    return job.result


@dataclass
class _Node:
    entry: Entry
    children: list["_Node"] = field(default_factory=list)
    error: Exception | None = None  # the folder could not be listed


def _scan(job: _Job, folder: str, entries: list[Entry]) -> list[_Node]:
    nodes = []
    for entry in entries:
        job.check_cancel()
        node = _Node(entry)
        if entry.is_dir and is_plain_name(entry.name):
            path = _join(folder, entry.name)
            try:
                node.children = _scan(job, path, job.session.list_dir(path, timeout=job.timeout))
            except (RemoteError, OSError) as exc:
                node.error = exc
        nodes.append(node)
    return nodes


def _file_bytes(node: _Node) -> int:
    if node.entry.is_dir:
        return sum(_file_bytes(c) for c in node.children)
    return node.entry.size


def _download(job: _Job, folder: str, nodes: list[_Node], local: str) -> None:
    for node in nodes:
        entry = node.entry
        job.check_cancel()
        source = _join(folder, entry.name)
        if not is_plain_name(entry.name):
            job.fail(source, f"unsafe name {entry.name!r}: not received")
            continue
        target = os.path.join(local, entry.name)
        try:
            if entry.is_dir:
                if node.error:
                    raise node.error
                os.makedirs(target, exist_ok=True)
                _download(job, source, node.children, target)
            else:
                job.report(entry.name)
                job.session.get_file(
                    source,
                    target,
                    timeout=job.timeout,
                    progress=lambda n, name=entry.name: job.report(name, n),
                )
                job.finished(entry.size)
                job.report(entry.name)
                written = os.path.getsize(target)
                if written != entry.size:
                    job.fail(source, f"received {written} bytes, expected {entry.size}")
        except (ConnectionError, TimeoutError):
            job.lose(source, "file not received")
        except (RemoteError, OSError) as exc:
            job.fail(source, str(exc))


# -- remove
def remove(
    session: Session,
    next_dir: str,
    entries: list[Entry],
    progress: Progress | None = None,
    cancel: Callable[[], bool] | None = None,
    timeout: float = 60,
) -> Result:
    """Delete Next entries from `next_dir`, folders with their content (no recycle bin).

    The Next has no recursive delete: each folder is listed, its files deleted, then the
    folder itself, bottom-up. Progress counts items. Cancel is honoured between items."""
    job = _Job(session, progress, cancel, timeout, 0)
    try:
        nodes = _scan(job, next_dir, entries)
        job.set_total(sum(_item_count(n) for n in nodes))
        _delete(job, next_dir, nodes)
    except _Stop:
        pass
    return job.result


def _item_count(node: _Node) -> int:
    return 1 + sum(_item_count(c) for c in node.children)


def _delete(job: _Job, folder: str, nodes: list[_Node], counted: bool = True) -> None:
    for node in nodes:
        entry = node.entry
        job.check_cancel()
        path = _join(folder, entry.name)
        if not is_plain_name(entry.name):
            job.fail(path, f"unsafe name {entry.name!r}: not deleted")
            continue
        try:
            if entry.is_dir:
                if node.error:
                    raise node.error
                _delete(job, path, node.children, counted)
                job.session.remove_dir(path, timeout=job.timeout)
            else:
                job.session.remove_file(path, timeout=job.timeout)
        except (RemoteError, OSError) as exc:
            job.fail(path, str(exc))
        if counted:
            job.finished(1)
            job.report(entry.name)


def make_folder(session: Session, next_dir: str, name: str, timeout: float = 60) -> Result:
    """Create the folder `name` inside `next_dir`."""
    return _one(next_dir, name, lambda path: session.make_dir(path, timeout=timeout))


def rename(session: Session, next_dir: str, old: str, new: str, timeout: float = 60) -> Result:
    """Rename `old` to `new` inside `next_dir`."""
    return _one(next_dir, new, lambda _path: session.rename(_join(next_dir, old), _join(next_dir, new), timeout=timeout))


def _one(folder: str, name: str, action: Callable[[str], None]) -> Result:
    result = Result()
    path = _join(folder, name)
    if not is_plain_name(name):
        result.failures.append(Failure(path, f"unsafe name {name!r}"))
        return result
    try:
        action(path)
    except (RemoteError, OSError) as exc:
        result.failures.append(Failure(path, str(exc)))
    return result


# -- copy and move inside the Next
def copy(
    session: Session,
    next_dir: str,
    entries: list[Entry],
    target_dir: str,
    progress: Progress | None = None,
    cancel: Callable[[], bool] | None = None,
    timeout: float = 60,
) -> Result:
    """Copy Next entries from `next_dir` into `target_dir` on the Next; no data crosses the wire.
    An existing name is never overwritten."""
    return _transfer(session, next_dir, entries, target_dir, progress, cancel, timeout, move=False)


def move(
    session: Session,
    next_dir: str,
    entries: list[Entry],
    target_dir: str,
    progress: Progress | None = None,
    cancel: Callable[[], bool] | None = None,
    timeout: float = 60,
) -> Result:
    """Move Next entries into `target_dir`: a rename on the same drive; across drives a copy,
    a size check and only then the delete of the source. Any failure keeps the source."""
    return _transfer(session, next_dir, entries, target_dir, progress, cancel, timeout, move=True)


def _transfer(session, next_dir, entries, target_dir, progress, cancel, timeout, move: bool) -> Result:
    job = _Job(session, progress, cancel, timeout, len(entries))
    try:
        try:
            existing = {e.name.lower() for e in session.list_dir(target_dir, timeout=timeout)}
        except (RemoteError, OSError) as exc:
            for entry in entries:
                job.fail(_join(next_dir, entry.name), f"cannot list {target_dir}: {exc}")
            return job.result
        for entry in entries:
            job.check_cancel()
            source, target = _join(next_dir, entry.name), _join(target_dir, entry.name)
            reason = _refusal(next_dir, entry, target_dir, existing)
            if reason:
                job.fail(source, reason)
            elif move and _drive(source) == _drive(target):
                _guarded(job, source, lambda: session.rename(source, target, timeout=timeout))
            elif move:
                _move_across(job, source, target, entry)
            else:
                _guarded(job, source, lambda: session.copy(source, target, timeout=timeout))
            job.finished(1)
            job.report(entry.name)
    except _Stop:
        pass
    return job.result


def _refusal(next_dir: str, entry: Entry, target_dir: str, existing: set[str]) -> str:
    if not is_plain_name(entry.name):
        return f"unsafe name {entry.name!r}"
    folder, target = _norm(next_dir), _norm(target_dir)
    source = _norm(_join(next_dir, entry.name))
    if folder == target:
        return "already in that folder"
    if target == source or target.startswith(source + "/"):
        return "cannot go into itself"
    if entry.name.lower() in existing:
        return "a file or folder of that name already exists there"
    return ""


def _guarded(job: _Job, source: str, action: Callable[[], None]) -> None:
    try:
        action()
    except (RemoteError, OSError) as exc:
        job.fail(source, str(exc))


def _move_across(job: _Job, source: str, target: str, entry: Entry) -> None:
    """Copy, check the size, then delete the source; the source is kept on any doubt."""
    session, timeout = job.session, job.timeout
    try:
        session.copy(source, target, timeout=timeout)
        expected, found = _measure(job, source, entry), _measure(job, target, entry)
    except (RemoteError, OSError) as exc:
        job.fail(source, f"{exc}; source kept")
        return
    if expected != found:
        job.fail(source, f"copy differs from the source ({found} against {expected}); source kept")
        return
    node = _scan(job, _parent(source), [entry])[0]
    _delete(job, _parent(source), [node], counted=False)  # the caller counts one step per entry


def _measure(job: _Job, path: str, entry: Entry) -> tuple[int, int]:
    """(files, bytes) under `path`, from fresh listings."""
    if not entry.is_dir:
        for e in job.session.list_dir(_parent(path), timeout=job.timeout):
            if e.name == entry.name:
                return 1, e.size
        raise RemoteError(f"{path} not found after the copy")
    files = size = 0
    for e in job.session.list_dir(path, timeout=job.timeout):
        if e.is_dir:
            f, b = _measure(job, _join(path, e.name), e)
        else:
            f, b = 1, e.size
        files, size = files + f, size + b
    return files, size


def _drive(path: str) -> str:
    return path[:2].lower()


def _norm(path: str) -> str:
    return path.lower().rstrip("/")


def _parent(path: str) -> str:
    head = path.rstrip("/").rpartition("/")[0]
    return head if len(head) > 2 else head + "/"


# -- helpers
def is_plain_name(name: str) -> bool:
    """A name the Next sent that stays one component inside the Local folder."""
    return name not in ("", ".", "..") and not any(c in name for c in "/\\:\0")


def _local_size(path: str, ancestors: tuple[str, ...] = ()) -> int:
    """Bytes `send` will upload under `path`, walking folders as `send` does."""
    if not os.path.isdir(path):
        return _size_or_zero(path)
    real = os.path.realpath(path)
    if real in ancestors:
        return 0
    try:
        names = os.listdir(path)
    except OSError:
        return 0
    return sum(_local_size(os.path.join(path, n), ancestors + (real,)) for n in names)


def _size_or_zero(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:  # a broken symlink: reported when its turn comes
        return 0


def _base(path: str) -> str:
    return os.path.basename(path.rstrip(os.sep))


def _join(folder: str, name: str) -> str:
    return folder.rstrip("/") + "/" + name

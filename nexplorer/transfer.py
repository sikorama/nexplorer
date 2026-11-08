"""Send Local entries to the Next and receive Next entries into Local (Qt-free).

Nothing here ever deletes anything on Local. `progress(name, percent)` and
`cancel()` are called from the thread that runs the transfer or from the
Session's thread: callers hand results to their own thread themselves."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable

from nexplorer.protocol import Cancelled, Entry, RemoteError, Session

Progress = Callable[[str, int], None]


@dataclass
class Failure:
    name: str
    reason: str


@dataclass
class Result:
    failures: list[Failure] = field(default_factory=list)
    cancelled: bool = False


class _Stop(Exception):
    """The user cancelled: unwind out of the walk."""


class _Job:
    def __init__(self, session: Session, progress: Progress | None, cancel, timeout: float, total: int):
        self.session, self.timeout = session, timeout
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
) -> Result:
    """Upload files and folders (recursively) into `next_dir` on the Next."""
    job = _Job(session, progress, cancel, timeout, sum(_local_size(p) for p in local_paths))
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
            try:
                size = os.path.getsize(local)
                job.report(name)
                job.session.put_file(
                    local,
                    _join(folder, name),
                    timeout=job.timeout,
                    progress=lambda n, name=name: job.report(name, n),
                    cancel=job._cancel,
                )
                sent[name.lower()] = (name, size)
                job.finished(size)
                job.report(name)
            except Cancelled:
                job.result.cancelled = True
                job.fail(_join(folder, name), _partial_reason("cancelled", job, folder, name))
                raise _Stop from None
            except (RemoteError, OSError) as exc:
                job.fail(_join(folder, name), _partial_reason(str(exc), job, folder, name))
    finally:
        _check_sizes(job, folder, sent)


def _check_sizes(job: _Job, folder: str, sent: dict[str, tuple[str, int]]) -> None:
    if not sent:
        return
    try:
        found = {e.name.lower(): e.size for e in job.session.list_dir(folder, timeout=job.timeout)}
    except (RemoteError, OSError) as exc:  # a dead Session or a timeout too
        for name, _ in sent.values():
            job.fail(_join(folder, name), f"size not checked: {exc}")
        return
    for key, (name, expected) in sent.items():
        if found.get(key) != expected:
            job.fail(
                _join(folder, name),
                f"size on the Next is {found.get(key, 'missing')}, expected {expected}",
            )


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
        if entry.is_dir and _safe_name(entry.name):
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
        if not _safe_name(entry.name):
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
        except (RemoteError, OSError) as exc:
            job.fail(source, str(exc))


# -- helpers
def _safe_name(name: str) -> bool:
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

"""Operations on Local entries (Qt-free), reporting like `transfer`: one `Result`, one
`Failure` per entry that did not go. Nothing is ever replaced: a name that exists is refused,
except folders, which merge. The trash is a collaborator: any callable taking a path."""
from __future__ import annotations

import os
import shutil
from typing import Callable

from nexplorer.i18n import tr
from nexplorer.transfer import Failure, Progress, Result, is_plain_name

Trash = Callable[[str], None]


def system_trash(path: str) -> None:
    """Send `path` to the system trash (raises when there is none)."""
    from send2trash import send2trash

    send2trash(path)


def _reason(exc: Exception) -> str:
    return getattr(exc, "strerror", None) or str(exc) or exc.__class__.__name__


def _is_dir(path: str) -> bool:
    return os.path.isdir(path) and not os.path.islink(path)


def delete_path(path: str) -> None:
    """Remove a file, a link or a folder with its content."""
    if _is_dir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def _each(names: list[str], progress: Progress | None, cancel: Callable[[], bool] | None, one) -> Result:
    result = Result()
    for index, name in enumerate(names):
        if cancel is not None and cancel():
            result.cancelled = True
            break
        if progress is not None:
            progress(name, index * 100 // len(names))
        try:
            result.failures.extend(one(name))
        except Exception as exc:  # noqa: BLE001 - one entry's failure never stops the others
            result.failures.append(Failure(name, _reason(exc)))
    if progress is not None and not result.cancelled:
        progress("", 100)
    return result


def _invalid(name: str, new: str) -> Result | None:
    """A refusal when `new` is not a plain name (no separator, no `..`), else None."""
    return None if is_plain_name(new) else Result([Failure(name, tr("Invalid name"))])


def make_folder(folder: str, name: str) -> Result:
    if (refused := _invalid(name, name)) is not None:
        return refused
    try:
        os.mkdir(os.path.join(folder, name))
    except OSError as exc:
        return Result([Failure(name, _reason(exc))])
    return Result()


def rename(folder: str, old: str, new: str) -> Result:
    if (refused := _invalid(old, new)) is not None:
        return refused
    source, target = os.path.join(folder, old), os.path.join(folder, new)
    try:
        if os.path.lexists(target) and not (os.path.exists(source) and os.path.samefile(source, target)):
            return Result([Failure(old, tr("already exists"))])
        os.rename(source, target)
    except OSError as exc:
        return Result([Failure(old, _reason(exc))])
    return Result()


def _each_in(folder: str, names: list[str], act: Callable[[str], None], progress, cancel) -> Result:
    """Apply `act` to the path of each entry; a raised error is that entry's failure."""

    def one(name: str) -> list[Failure]:
        act(os.path.join(folder, name))
        return []

    return _each(names, progress, cancel, one)


def trash_entries(
    folder: str, names: list[str], trash: Trash, progress: Progress | None = None, cancel=None
) -> Result:
    """Send the entries to the trash; the failures are the ones the trash could not take."""
    return _each_in(folder, names, trash, progress, cancel)


def delete_entries(folder: str, names: list[str], progress: Progress | None = None, cancel=None) -> Result:
    """Delete for good, folders with their content."""
    return _each_in(folder, names, delete_path, progress, cancel)


def _merge(source: str, target: str, move: bool, label: str) -> list[Failure]:
    if os.path.lexists(target):
        if not (_is_dir(source) and _is_dir(target)):
            return [Failure(label, tr("already exists"))]
        failures = []
        for child in sorted(os.listdir(source)):
            try:
                failures += _merge(os.path.join(source, child), os.path.join(target, child), move, f"{label}/{child}")
            except OSError as exc:
                failures.append(Failure(f"{label}/{child}", _reason(exc)))
        if move:
            try:
                os.rmdir(source)  # only once everything left it; a refused child keeps it
            except OSError:
                pass
        return failures
    try:
        if move:
            shutil.move(source, target)
        elif _is_dir(source):
            shutil.copytree(source, target, symlinks=True)
        else:
            shutil.copy2(source, target, follow_symlinks=False)
    except OSError as exc:
        return [Failure(label, _reason(exc))]
    return []


def _place(folder: str, names: list[str], target: str, move: bool, progress, cancel) -> Result:
    here = os.path.realpath(folder)
    destination = os.path.realpath(target)

    def one(name: str) -> list[Failure]:
        source = os.path.join(folder, name)
        if destination == here:
            return [Failure(name, tr("already in that folder"))]
        real = os.path.realpath(source)
        if _is_dir(source) and (destination == real or destination.startswith(real + os.sep)):
            return [Failure(name, tr("cannot go into itself"))]
        return _merge(source, os.path.join(target, name), move, name)

    return _each(names, progress, cancel, one)


def move(folder: str, names: list[str], target: str, progress: Progress | None = None, cancel=None) -> Result:
    return _place(folder, names, target, True, progress, cancel)


def copy(folder: str, names: list[str], target: str, progress: Progress | None = None, cancel=None) -> Result:
    return _place(folder, names, target, False, progress, cancel)

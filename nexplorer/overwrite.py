"""Find what a send or a receive would overwrite, and apply the user's answers (Qt-free).

A name collides when the destination side already has it, compared by that side's
own spelling rules: case-insensitive on the Next, the Local file system's own rules
on Local. Folders merge: a folder meeting a folder is never a collision itself, only
the files inside it that already exist. A listing that fails raises (`RemoteError` or
`OSError`): the caller must not run the batch without the check."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from nexplorer.protocol import Entry, Session
from nexplorer.transfer import is_plain_name

OVERWRITE, SKIP, CANCEL = "overwrite", "skip", "cancel"

# (destination path, collisions left including this one) -> (answer, apply to all)
Ask = Callable[[str, int], tuple[str, bool]]


def send_collisions(session: Session, paths: list[str], next_dir: str, timeout: float = 60) -> list[str]:
    """Next paths that sending `paths` into `next_dir` would overwrite."""
    found: list[str] = []
    _send_level(session, paths, next_dir, found, timeout, ())
    return found


def _send_level(session, paths, folder, found, timeout, ancestors) -> None:
    existing = {e.name.lower(): e for e in session.list_dir(folder, timeout=timeout)}
    for path in paths:
        name = os.path.basename(path.rstrip(os.sep))
        hit = existing.get(name.lower())
        if hit is None:
            continue
        target = folder.rstrip("/") + "/" + name
        if os.path.isdir(path) and hit.is_dir:
            real = os.path.realpath(path)
            if real in ancestors:
                continue  # a symlink loop: the transfer reports it
            children = [os.path.join(path, n) for n in sorted(os.listdir(path))]
            _send_level(session, children, target, found, timeout, ancestors + (real,))
        else:
            found.append(target)


def receive_collisions(
    session: Session, next_dir: str, entries: list[Entry], local_dir: str, timeout: float = 60
) -> list[str]:
    """Local paths that receiving `entries` from `next_dir` into `local_dir` would overwrite."""
    found: list[str] = []
    _receive_level(session, next_dir, entries, local_dir, found, timeout)
    return found


def _receive_level(session, folder, entries, local, found, timeout) -> None:
    existing = {os.path.normcase(n): n for n in os.listdir(local)}
    for entry in entries:
        if not is_plain_name(entry.name):
            continue  # refused by the transfer itself
        name = existing.get(os.path.normcase(entry.name))
        if name is None:
            continue
        target = os.path.join(local, name)
        if entry.is_dir and os.path.isdir(target):
            source = folder.rstrip("/") + "/" + entry.name
            _receive_level(session, source, session.list_dir(source, timeout=timeout), target, found, timeout)
        else:
            found.append(target)


@dataclass
class Decision:
    skip: list[str]
    cancelled: bool = False


def decide(collisions: list[str], ask: Ask) -> Decision:
    """Ask about each collision in turn; "apply to all" answers the ones left."""
    skip: list[str] = []
    standing = ""
    for index, path in enumerate(collisions):
        answer = standing
        if not answer:
            answer, everyone = ask(path, len(collisions) - index)
            if answer == CANCEL:
                return Decision([], cancelled=True)
            if everyone:
                standing = answer
        if answer == SKIP:
            skip.append(path)
    return Decision(skip)

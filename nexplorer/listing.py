"""Sorting shared by the Local and Next panes."""
from __future__ import annotations

from typing import Iterable

from nexplorer.protocol import Entry


def _extension(entry: Entry) -> str:
    return entry.name.rpartition(".")[2].lower() if "." in entry.name.strip(".") else ""


_KEYS = {
    "name": lambda e: (e.name.lower(),),
    "size": lambda e: (e.size, e.name.lower()),
    "type": lambda e: (_extension(e), e.name.lower()),
}


def sort_entries(entries: Iterable[Entry], by: str, descending: bool = False) -> list[Entry]:
    """Folders first, then files; each group sorted by name, size or type."""
    key = _KEYS[by]
    entries = list(entries)
    groups = [[e for e in entries if e.is_dir], [e for e in entries if not e.is_dir]]
    return [e for group in groups for e in sorted(group, key=key, reverse=descending)]

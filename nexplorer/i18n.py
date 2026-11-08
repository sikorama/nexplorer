"""Translation: one function keyed by the English text, which is also the fallback."""
from __future__ import annotations

import json
from pathlib import Path

_DEFAULT_DIR = Path(__file__).parent / "locales"
_catalogue: dict[str, str] = {}


def set_language(code: str, catalogue_dir: Path | None = None) -> None:
    global _catalogue
    path = (catalogue_dir or _DEFAULT_DIR) / f"{code}.json"
    try:
        _catalogue = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _catalogue = {}


def tr(text: str) -> str:
    return _catalogue.get(text, text)


def available_languages(catalogue_dir: Path | None = None) -> list[str]:
    """Language codes with a catalogue, plus English (the built-in text)."""
    found = {p.stem for p in (catalogue_dir or _DEFAULT_DIR).glob("*.json")}
    return sorted(found | {"en"})

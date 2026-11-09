"""Light and dark themes: two palettes, one stylesheet, applied application-wide."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# Every palette defines the same roles (a test checks it).
PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "window": "#f3f4f6",
        "base": "#ffffff",
        "alt_base": "#f1f5f9",
        "text": "#1f2937",
        "disabled_text": "#9ca3af",
        "button": "#e5e7eb",
        "border": "#d1d5db",
        "highlight": "#2563eb",
        "highlighted_text": "#ffffff",
        "accent": "#2563eb",
        "link": "#1d4ed8",
        "connected": "#16a34a",
        "state_only_local": "#1d4ed8",
        "state_only_next": "#7c3aed",
        "state_different": "#b45309",
        "state_identical": "#15803d",
        "state_unverified": "#6b7280",
    },
    "dark": {
        "window": "#1f2329",
        "base": "#14171b",
        "alt_base": "#1b1f24",
        "text": "#e5e7eb",
        "disabled_text": "#6b7280",
        "button": "#2d333b",
        "border": "#3b424c",
        "highlight": "#3b82f6",
        "highlighted_text": "#ffffff",
        "accent": "#60a5fa",
        "link": "#93c5fd",
        "connected": "#4ade80",
        "state_only_local": "#7db4ff",
        "state_only_next": "#c4a1ff",
        "state_different": "#fbbf24",
        "state_identical": "#4ade80",
        "state_unverified": "#9ca3af",
    },
}


def system_scheme() -> Qt.ColorScheme:
    """The desktop's colour scheme as Qt reports it."""
    return QApplication.styleHints().colorScheme()


def resolve(theme: str, scheme: Qt.ColorScheme = Qt.ColorScheme.Unknown) -> str:
    """The palette name for a setting: System follows `scheme`, and falls back to light."""
    if theme == "system":
        return "dark" if scheme == Qt.ColorScheme.Dark else "light"
    return theme if theme in PALETTES else "light"


def palette(name: str) -> QPalette:
    c = {k: QColor(v) for k, v in PALETTES[name].items()}
    p = QPalette()
    for role, key in (
        (QPalette.Window, "window"), (QPalette.Base, "base"), (QPalette.AlternateBase, "alt_base"),
        (QPalette.WindowText, "text"), (QPalette.Text, "text"), (QPalette.ButtonText, "text"),
        (QPalette.Button, "button"), (QPalette.Highlight, "highlight"),
        (QPalette.HighlightedText, "highlighted_text"), (QPalette.Link, "link"),
        (QPalette.ToolTipBase, "base"), (QPalette.ToolTipText, "text"),
    ):  # fmt: skip
        p.setColor(role, c[key])
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, c["disabled_text"])
    return p


def stylesheet(name: str) -> str:
    c = PALETTES[name]
    return f"""
QToolBar {{ background: {c['window']}; border: none; border-bottom: 1px solid {c['border']}; spacing: 4px; padding: 3px; }}
QToolButton {{ border: 1px solid transparent; border-radius: 4px; padding: 3px; }}
QToolButton:hover {{ background: {c['button']}; border-color: {c['border']}; }}
QToolButton:pressed {{ background: {c['border']}; }}
QMenuBar {{ background: {c['window']}; }}
QMenuBar::item {{ padding: 4px 10px; background: transparent; }}
QMenuBar::item:selected {{ background: {c['button']}; border-radius: 4px; }}
QMenu {{ background: {c['base']}; border: 1px solid {c['border']}; padding: 4px; }}
QMenu::item {{ padding: 4px 22px 4px 8px; border-radius: 3px; }}
QMenu::item:selected {{ background: {c['highlight']}; color: {c['highlighted_text']}; }}
QMenu::item:disabled {{ color: {c['disabled_text']}; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 4px 6px; }}
QStatusBar {{ background: {c['window']}; border-top: 1px solid {c['border']}; }}
QTreeWidget {{ background: {c['base']}; alternate-background-color: {c['alt_base']}; border: 1px solid {c['border']}; }}
QHeaderView::section {{ background: {c['button']}; padding: 4px; border: none; border-right: 1px solid {c['border']}; }}
QLineEdit, QComboBox {{ background: {c['base']}; border: 1px solid {c['border']}; border-radius: 4px; padding: 3px 6px; }}
QPushButton {{ background: {c['button']}; border: 1px solid {c['border']}; border-radius: 4px; padding: 4px 12px; }}
QPushButton:hover {{ border-color: {c['accent']}; }}
QPushButton:disabled {{ color: {c['disabled_text']}; }}
QProgressBar {{ border: 1px solid {c['border']}; border-radius: 4px; text-align: center; background: {c['base']}; }}
QProgressBar::chunk {{ background: {c['accent']}; border-radius: 3px; }}
QSplitter::handle {{ background: {c['border']}; }}
QFrame#card {{ background: {c['base']}; border: 1px solid {c['border']}; border-radius: 10px; }}
QDialog {{ background: {c['window']}; }}
"""


def apply(app: QApplication, theme: str, scheme: Qt.ColorScheme | None = None) -> str:
    """Re-style the whole application; returns the palette name actually used.

    `scheme` is what System follows (the desktop's scheme when omitted)."""
    name = resolve(theme, system_scheme() if scheme is None else scheme)
    app.setStyle("Fusion")
    app.setPalette(palette(name))
    app.setStyleSheet(stylesheet(name))
    return name


def icon_colour(name: str) -> QColor:
    return QColor(PALETTES[name]["text"])


def state_colour(name: str, state: str) -> QColor | None:
    """The colour of a Compare state in a palette; None for states shown in the default colour."""
    key = "state_" + state.replace("-", "_")
    return QColor(PALETTES[name][key]) if key in PALETTES[name] else None

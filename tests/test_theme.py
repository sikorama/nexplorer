"""Themes: the setting, the palettes, and the window following them."""
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt

from nexplorer import i18n
from nexplorer.settings import Settings, load, save
from nexplorer.ui import theme
from nexplorer.ui.main_window import MainWindow
from tests.conftest import dispose, pump
from tests.fake_next import FakeNext
from tests.test_window_compare import NEXT_FS, local_folder, prepare
from tests.test_window_settings import opened

DARK, LIGHT = Qt.ColorScheme.Dark, Qt.ColorScheme.Light


def test_the_theme_defaults_to_light_round_trips_and_rejects_bad_values(tmp_path):
    path = tmp_path / "settings.json"
    assert Settings().theme == "light"
    for choice in ("light", "dark", "system"):
        save(Settings(theme=choice), path)
        assert load(path).theme == choice
    for bad in ("blue", "", 3, None, ["dark"]):
        path.write_text(json.dumps({"theme": bad, "language": "fr"}))
        assert load(path).theme == "light" and load(path).language == "fr"


def test_both_palettes_define_the_same_colour_roles():
    assert set(theme.PALETTES["light"]) == set(theme.PALETTES["dark"])
    assert theme.PALETTES["light"] != theme.PALETTES["dark"]


def test_system_follows_the_desktop_scheme_and_falls_back_to_light():
    assert theme.resolve("system", DARK) == "dark"
    assert theme.resolve("system", LIGHT) == "light"
    assert theme.resolve("system", Qt.ColorScheme.Unknown) == "light"
    assert theme.resolve("dark", LIGHT) == "dark"


def test_the_theme_strings_are_translated_in_french():
    i18n.set_language("fr")
    try:
        for text in ("Theme", "Light", "Dark", "System"):
            assert i18n.tr(text) != text
    finally:
        i18n.set_language("en")


def test_choosing_a_theme_in_settings_restyles_the_open_window_at_once(app, tmp_path):
    with opened(app, tmp_path / "s.json", ask_settings=lambda s: Settings(**{**s.__dict__, "theme": "dark"})) as (w, _):
        assert w.current_theme() == "light"
        light_text = app.palette().color(app.palette().ColorRole.Window).name()
        w.open_settings()
        assert w.current_theme() == "dark"
        assert app.palette().color(app.palette().ColorRole.Window).name() != light_text
        assert load(tmp_path / "s.json").theme == "dark"
    theme.apply(app, "light")


def test_the_icons_are_tinted_to_the_theme(app, tmp_path):
    with opened(app, tmp_path / "s.json") as (w, _):
        before = w._actions.action("copy").icon().pixmap(16, 16).toImage()
        w.apply_settings(Settings(theme="dark"))
        assert w._actions.action("copy").icon().pixmap(16, 16).toImage() != before
    theme.apply(app, "light")


def test_the_active_border_and_the_connection_dot_use_the_palette_and_follow_the_theme(app, tmp_path):
    path = local_folder(tmp_path)
    with opened(app, path) as (w, listener):
        nxt = prepare(app, w, listener, tmp_path, NEXT_FS)
        for choice in ("light", "dark", "light"):
            w.apply_settings(Settings(theme=choice, local_folder=str(tmp_path / "local")))
            colours = theme.PALETTES[choice]
            assert colours["accent"] in w.local_pane().list_view().styleSheet()
            assert colours["connected"] in w.connection_text()
            assert "2ecc40" not in w.connection_text()
        nxt.drop()
    theme.apply(app, "light")


def test_system_theme_follows_the_desktop_when_it_changes(app, tmp_path):
    scheme = [LIGHT]
    from PySide6.QtCore import QObject

    from nexplorer.protocol import Listener

    listener = Listener(host="127.0.0.1", port=0)
    listener.start()
    w = MainWindow(listener, local_addresses=lambda: [], color_scheme=lambda: scheme[0])
    try:
        w.apply_settings(Settings(theme="system"))
        assert w.current_theme() == "light"
        scheme[0] = DARK
        w._on_scheme_changed()
        assert w.current_theme() == "dark"
        w.apply_settings(Settings(theme="light"))
        w._on_scheme_changed()
        assert w.current_theme() == "light"
    finally:
        w.close()
        dispose(app, w)
        listener.stop()
        theme.apply(app, "light")


@pytest.mark.parametrize("choice", ["light", "dark"])
def test_compare_colours_each_state_readably_in_both_themes(app, tmp_path, choice):
    path = local_folder(tmp_path)
    save(Settings(local_folder=str(tmp_path / "local"), theme=choice), path)
    with opened(app, path) as (w, listener):
        nxt = prepare(app, w, listener, tmp_path, NEXT_FS)
        w.compare()
        colours = {n: w.compare_state_colour(n) for n in ("up.tap", "down.tap", "clash.tap", "same.tap")}
        assert all(c is not None for c in colours.values())
        assert len({c.name() for c in colours.values()}) == 4  # distinct states, distinct colours
        base = theme.PALETTES[choice]["base"]
        for c in colours.values():
            assert _contrast(c.name(), base) >= 3.0
        nxt.drop()
    theme.apply(app, "light")


def test_compare_colours_follow_a_theme_change_while_open(app, tmp_path):
    path = local_folder(tmp_path)
    with opened(app, path) as (w, listener):
        nxt = prepare(app, w, listener, tmp_path, NEXT_FS)
        w.compare()
        before = w.compare_state_colour("up.tap").name()
        w.apply_settings(Settings(theme="dark", local_folder=str(tmp_path / "local")))
        assert w.compare_state_colour("up.tap").name() != before
        nxt.drop()
    theme.apply(app, "light")


def _luminance(hex_colour: str) -> float:
    rgb = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)

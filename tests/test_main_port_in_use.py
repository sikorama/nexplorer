import socket

import pytest

from nexplorer import __main__ as entry
from nexplorer import i18n, settings


@pytest.fixture
def occupied_port(monkeypatch, tmp_path):
    """A port another program holds, and a private settings file (language set by the test)."""
    holder = socket.socket()
    holder.bind(("0.0.0.0", 0))
    holder.listen()
    port = holder.getsockname()[1]
    monkeypatch.setattr(entry, "PORT", port)
    path = tmp_path / "settings.json"
    monkeypatch.setattr(settings, "config_path", lambda: path)
    yield port, path
    holder.close()
    i18n.set_language("en")


def test_port_in_use_shows_a_dialog_and_still_writes_stderr(occupied_port, capsys, app):
    port, _ = occupied_port
    shown = []

    code = entry.main(show_error=shown.append)

    assert code == 1
    assert len(shown) == 1
    assert shown[0].startswith(f"Cannot listen on port {port}: ")
    assert shown[0] in capsys.readouterr().err


def test_port_in_use_dialog_is_translated_in_french(occupied_port, app):
    port, path = occupied_port
    settings.save(settings.Settings(language="fr"), path)
    shown = []

    entry.main(show_error=shown.append)

    assert shown[0].startswith(f"Impossible d'écouter sur le port {port}: ")

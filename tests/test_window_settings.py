import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from contextlib import contextmanager

import pytest

from nexplorer.protocol import Listener
from nexplorer.settings import Settings, load, save
from nexplorer.ui.main_window import MainWindow
from tests.conftest import dispose, pump
from tests.fake_next import FakeNext

FS = {"c:/games": None, "c:/games/a.tap": b"x" * 10, "c:/.hidden": b"h", "c:/b.txt": b"b" * 5}


@pytest.fixture
def local(tmp_path):
    folder = tmp_path / "local"
    (folder / "sub").mkdir(parents=True)
    (folder / "big.bin").write_bytes(b"x" * 500)
    (folder / "small.bin").write_bytes(b"x")
    (folder / ".git").mkdir()
    return folder


@contextmanager
def opened(app, path, ask_settings=None):
    listener = Listener(host="127.0.0.1", port=0)
    listener.start()
    kwargs = {} if ask_settings is None else {"ask_settings": ask_settings}
    w = MainWindow(listener, local_addresses=lambda: [], settings_path=path, **kwargs)
    w.show()
    try:
        yield w, listener
    finally:
        w.close()
        dispose(app, w)
        listener.stop()


def connect(app, w, listener):
    nxt = FakeNext(listener.port, fs=FS, free_blocks={"C": 2048})
    nxt.connect()
    assert pump(app, lambda: w.next_pane_state() == "connected")
    return nxt


def test_reopens_on_the_last_local_folder_sort_and_geometry(app, tmp_path, local):
    path = tmp_path / "cfg" / "settings.json"
    save(Settings(local_folder=str(local), local_sort=("size", True), show_hidden=True), path)
    with opened(app, path) as (w, _):
        pane = w.local_pane()
        assert pump(app, lambda: pane.path() == str(local) and pane.names())
        assert pane.names() == ["sub", ".git", "big.bin", "small.bin"]
        w.resize(w.width(), 650)
    with opened(app, path) as (w, _):
        assert w.height() == 650


def test_hidden_files_are_hidden_by_default_and_shown_by_the_setting(app, tmp_path, local):
    path = tmp_path / "settings.json"
    save(Settings(local_folder=str(local)), path)
    with opened(app, path) as (w, _):
        pane = w.local_pane()
        assert pump(app, lambda: "big.bin" in pane.names())
        assert ".git" not in pane.names()
        w.apply_settings(Settings(local_folder=str(local), show_hidden=True))
        assert ".git" in pane.names()


def test_next_folder_is_restored_when_its_drive_exists(app, tmp_path):
    path = tmp_path / "settings.json"
    save(Settings(next_folder="c:/games", show_hidden=True), path)
    with opened(app, path) as (w, listener):
        nxt = connect(app, w, listener)
        assert pump(app, lambda: w.next_pane().path() == "c:/games" and w.next_pane().names() == ["a.tap"])
        nxt.drop()


def test_next_folder_on_an_unreported_drive_falls_back_to_the_drive_root(app, tmp_path):
    path = tmp_path / "settings.json"
    save(Settings(next_folder="d:/games"), path)
    with opened(app, path) as (w, listener):
        nxt = connect(app, w, listener)
        assert pump(app, lambda: w.next_pane().path() == "c:/" and w.next_pane().names())
        nxt.drop()


def test_closing_writes_folders_sort_and_choices_to_the_one_file(app, tmp_path, local):
    path = tmp_path / "cfg" / "settings.json"
    save(Settings(local_folder=str(local)), path)
    with opened(app, path) as (w, listener):
        nxt = connect(app, w, listener)
        assert pump(app, lambda: w.next_pane().names())
        w.next_pane().enter("games")
        assert pump(app, lambda: w.next_pane().path() == "c:/games")
        w.next_pane().sort_by("size")
        w.local_pane().sort_by("type")
        nxt.drop()
    saved = load(path)
    assert saved.local_folder == str(local)
    assert saved.next_folder == "c:/games"
    assert saved.next_sort == ("size", False)
    assert saved.local_sort == ("type", False)
    assert saved.geometry
    assert os.listdir(path.parent) == ["settings.json"]


def test_settings_dialog_changes_are_applied_and_saved(app, tmp_path, local):
    path = tmp_path / "settings.json"
    save(Settings(local_folder=str(local)), path)
    shown = []

    def dialog(current):
        shown.append(current)
        return Settings(**{**current.__dict__, "show_hidden": True, "crc_after_upload": True, "language": "fr"})

    with opened(app, path, ask_settings=dialog) as (w, _):
        pane = w.local_pane()
        assert pump(app, lambda: "big.bin" in pane.names())
        w.open_settings()
        assert shown[0].show_hidden is False
        assert ".git" in pane.names()
    saved = load(path)
    assert (saved.show_hidden, saved.crc_after_upload, saved.language) == (True, True, "fr")


def test_cancelled_settings_dialog_changes_nothing(app, tmp_path, local):
    path = tmp_path / "settings.json"
    save(Settings(local_folder=str(local)), path)
    with opened(app, path, ask_settings=lambda current: None) as (w, _):
        pane = w.local_pane()
        assert pump(app, lambda: "big.bin" in pane.names())
        w.open_settings()
        assert ".git" not in pane.names()


def test_a_corrupt_geometry_in_the_file_does_not_stop_the_app_starting(app, tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"geometry": "abc"}')
    with opened(app, path) as (w, _):
        assert w.isVisible()


def test_reconnecting_reopens_the_last_folder_visited(app, tmp_path):
    path = tmp_path / "settings.json"
    with opened(app, path) as (w, listener):
        nxt = connect(app, w, listener)
        assert pump(app, lambda: w.next_pane().names())
        w.next_pane().enter("games")
        assert pump(app, lambda: w.next_pane().path() == "c:/games")
        nxt.drop()
        assert pump(app, lambda: w.next_pane_state() == "waiting")
        nxt = connect(app, w, listener)
        assert pump(app, lambda: w.next_pane().path() == "c:/games" and w.next_pane().names() == ["a.tap"])
        nxt.drop()


def test_a_remembered_folder_that_is_gone_falls_back_to_the_drive_root(app, tmp_path):
    path = tmp_path / "settings.json"
    save(Settings(next_folder="c:/vanished"), path)
    with opened(app, path) as (w, listener):
        nxt = connect(app, w, listener)
        assert pump(app, lambda: w.next_pane().path() == "c:/" and w.next_pane().names())
        assert w.next_pane().error() == ""
        nxt.drop()


def test_free_space_shown_is_that_of_the_drive_reopened(app, tmp_path):
    path = tmp_path / "settings.json"
    save(Settings(next_folder="m:/"), path)
    with opened(app, path) as (w, listener):
        nxt = FakeNext(listener.port, fs={"m:/x": b"1"}, drives="CM", free_blocks={"C": 2048, "M": 4})
        nxt.connect()
        assert pump(app, lambda: w.next_pane().path() == "m:/")
        assert pump(app, lambda: w.next_pane().free_space_text() != "")
        assert w.next_pane().free_space_text() == "2.0 KB free"
        nxt.drop()

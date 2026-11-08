import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nexplorer.settings import Settings, save
from tests.conftest import pump
from tests.fake_next import FakeNext
from tests.test_window_settings import FS, opened


def connect_version(app, w, listener, version):
    nxt = FakeNext(listener.port, fs=FS, free_blocks={"C": 2048}, version=version)
    nxt.connect()
    assert pump(app, lambda: w.next_pane_state() == "connected")
    assert pump(app, lambda: "b.txt" in w.next_pane().names())
    return nxt


def settings_file(tmp_path, **kwargs):
    folder = tmp_path / "local"
    folder.mkdir()
    (folder / "b.txt").write_bytes(b"b" * 5)
    path = tmp_path / "settings.json"
    save(Settings(local_folder=str(folder), **kwargs), path)
    return path


def test_an_old_dot_greys_copy_cut_paste_and_says_which_version_to_install(app, tmp_path):
    with opened(app, settings_file(tmp_path)) as (w, listener):
        nxt = connect_version(app, w, listener, "5.1.0")
        assert pump(app, lambda: "5.9.2" in w.dot_notice())
        w.next_pane().select(["b.txt"])
        assert not w.copy_enabled() and not w.cut_enabled() and not w.paste_enabled()
        assert w.delete_enabled() and w.rename_enabled()
        w.copy_selected()
        w.paste()
        assert b"C" not in nxt.commands
        nxt.drop()


def test_a_dot_without_crc_greys_verify_and_never_receives_k(app, tmp_path):
    with opened(app, settings_file(tmp_path, crc_after_upload=True)) as (w, listener):
        nxt = connect_version(app, w, listener, "5.9.1")
        assert pump(app, lambda: "5.9.2" in w.dot_notice())
        w.next_pane().select(["b.txt"])
        assert w.copy_enabled()
        w.compare()
        assert not w.compare_verify_enabled()
        w.compare_verify()
        w.compare_back()
        w.send_selected()
        pump(app, lambda: w.operation_running(), timeout=0.5)
        assert pump(app, lambda: not w.operation_running(), timeout=5)
        assert b"K" not in nxt.commands
        nxt.drop()


def test_a_current_dot_leaves_every_action_and_shows_no_notice(app, tmp_path):
    with opened(app, settings_file(tmp_path)) as (w, listener):
        nxt = connect_version(app, w, listener, "5.9.14")
        assert pump(app, lambda: w.dot_version_known())
        w.next_pane().select(["b.txt"])
        assert w.copy_enabled() and w.cut_enabled() and w.rename_enabled()
        w.compare()
        assert w.compare_verify_enabled()
        assert w.dot_notice() == ""
        nxt.drop()


def test_an_unparseable_version_greys_nothing(app, tmp_path):
    with opened(app, settings_file(tmp_path)) as (w, listener):
        nxt = connect_version(app, w, listener, "weird")
        assert pump(app, lambda: w.dot_version_known())
        w.next_pane().select(["b.txt"])
        assert w.copy_enabled()
        w.compare()
        assert w.compare_verify_enabled() and w.dot_notice() == ""
        nxt.drop()


def test_nothing_is_ever_sent_to_update_the_dot(app, tmp_path):
    with opened(app, settings_file(tmp_path)) as (w, listener):
        nxt = connect_version(app, w, listener, "5.0.0")
        assert pump(app, lambda: "5.9.2" in w.dot_notice())
        assert b"U" not in nxt.commands and set(nxt.commands) <= {b"Y", b"L", b"W", b"Z"}
        nxt.drop()

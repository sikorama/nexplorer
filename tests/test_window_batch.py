import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nexplorer.settings import Settings, save
from tests.conftest import pump
from tests.fake_next import FakeNext
from tests.test_window_settings import opened


def connect(app, w, listener, **kwargs):
    nxt = FakeNext(listener.port, fs={"c:/dest": None}, free_blocks={"C": 2048}, **kwargs)
    nxt.connect()
    assert pump(app, lambda: w.next_pane_state() == "connected")
    assert pump(app, lambda: w.next_pane().path() == "c:/" and w.next_pane().names() == ["dest"])
    w.next_pane().enter("dest")
    assert pump(app, lambda: w.next_pane().path() == "c:/dest")
    return nxt


def send_and_wait(app, w, paths):
    w.drop_files(paths)
    assert pump(app, lambda: w.operation_running())
    assert pump(app, lambda: not w.operation_running(), timeout=10)


def test_the_crc_setting_makes_each_upload_verified_and_a_mismatch_is_reported(app, tmp_path):
    path = tmp_path / "settings.json"
    save(Settings(local_folder=str(tmp_path), crc_after_upload=True), path)
    (tmp_path / "bad.bin").write_bytes(b"b" * 50)
    with opened(app, path) as (w, listener):
        nxt = connect(app, w, listener, corrupt_puts_of=("bad.bin",))
        send_and_wait(app, w, [str(tmp_path / "bad.bin")])
        assert b"K" in nxt.commands
        assert "CRC" in w.summary_text() and "bad.bin" in w.summary_text()
        nxt.drop()


def test_without_the_crc_setting_no_crc_is_asked(app, tmp_path):
    path = tmp_path / "settings.json"
    save(Settings(local_folder=str(tmp_path)), path)
    (tmp_path / "bad.bin").write_bytes(b"b" * 50)
    with opened(app, path) as (w, listener):
        nxt = connect(app, w, listener, corrupt_puts_of=("bad.bin",))
        send_and_wait(app, w, [str(tmp_path / "bad.bin")])
        assert b"K" not in nxt.commands
        assert w.summary_text().startswith("Done")
        nxt.drop()


def test_a_session_lost_mid_batch_shows_the_partial_file_and_returns_to_the_waiting_screen(app, tmp_path):
    path = tmp_path / "settings.json"
    save(Settings(local_folder=str(tmp_path)), path)
    (tmp_path / "big.bin").write_bytes(b"x" * 2000)
    (tmp_path / "later.bin").write_bytes(b"y")
    with opened(app, path) as (w, listener):
        nxt = connect(app, w, listener, put_drops_at_chunk=("big.bin", 2))
        send_and_wait(app, w, [str(tmp_path / "big.bin"), str(tmp_path / "later.bin")])
        text = w.summary_text()
        assert "big.bin" in text and "1024 bytes" in text
        assert "later.bin" not in text
        assert "Session lost" in text.splitlines()[0]
        assert pump(app, lambda: w.next_pane_state() == "waiting")
        assert nxt.fs["c:/dest/big.bin"] == b"x" * 1024  # nothing deleted

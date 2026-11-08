import time

import pytest

from nexplorer.protocol import Listener, RemoteError
from tests.fake_next import FakeNext


@pytest.fixture
def listener():
    l = Listener(host="127.0.0.1", port=0)
    l.start()
    yield l
    l.stop()


def test_fake_next_connecting_opens_session_reporting_dot_version(listener):
    nxt = FakeNext(listener.port, version="5.9.14")
    assert nxt.connect() == b"Listening"
    session = listener.wait_session(timeout=2)
    assert session is not None
    assert session.dot_version(timeout=2) == "5.9.14"
    nxt.drop()


def test_second_next_is_told_busy_and_first_session_stays_usable(listener):
    first = FakeNext(listener.port, version="5.9.14")
    first.connect()
    session = listener.wait_session(timeout=2)
    second = FakeNext(listener.port)
    assert second.connect() == b"Busy"
    assert session.dot_version(timeout=2) == "5.9.14"
    first.drop()


def test_session_ends_when_next_presses_break(listener):
    nxt = FakeNext(listener.port)
    nxt.connect()
    session = listener.wait_session(timeout=2)
    nxt.bye()
    assert session.wait_closed(timeout=2)
    assert listener.current_session is None


def test_session_ends_when_next_vanishes(listener):
    nxt = FakeNext(listener.port)
    nxt.connect()
    session = listener.wait_session(timeout=2)
    nxt.drop()
    assert session.wait_closed(timeout=2)


def test_closing_session_makes_the_next_leave(listener):
    nxt = FakeNext(listener.port)
    nxt.connect()
    session = listener.wait_session(timeout=2)
    session.close()
    assert nxt.ended.wait(2)
    assert session.wait_closed(timeout=2)


def test_a_new_next_is_accepted_after_the_session_ended(listener):
    first = FakeNext(listener.port)
    first.connect()
    session = listener.wait_session(timeout=2)
    first.drop()
    session.wait_closed(timeout=2)
    again = FakeNext(listener.port)
    assert again.connect() == b"Listening"
    assert listener.wait_session(timeout=2) is not None
    again.drop()


def test_old_dot_that_ignores_ident_gives_unknown_version_and_session_stays_in_step(listener):
    nxt = FakeNext(listener.port, version="5.7.0", ignores=frozenset({b"Y"}))
    nxt.connect()
    session = listener.wait_session(timeout=2)
    assert session.dot_version(timeout=2) is None
    assert session.dot_version(timeout=2) is None
    assert not session.wait_closed(timeout=0.2)
    nxt.bye()
    assert session.wait_closed(timeout=2)


def test_command_in_flight_when_the_link_dies_fails_instead_of_hanging(listener):
    nxt = FakeNext(listener.port, drops_on=frozenset({b"Y"}))
    nxt.connect()
    session = listener.wait_session(timeout=2)
    with pytest.raises(ConnectionError):
        session.dot_version(timeout=2)


def test_command_on_a_closed_session_fails(listener):
    nxt = FakeNext(listener.port)
    nxt.connect()
    session = listener.wait_session(timeout=2)
    nxt.drop()
    session.wait_closed(timeout=2)
    with pytest.raises(ConnectionError):
        session.dot_version(timeout=2)


def test_command_that_timed_out_is_never_sent_later(listener):
    nxt = FakeNext(listener.port, poll_interval=0.3)
    nxt.connect()
    session = listener.wait_session(timeout=2)
    time.sleep(0.1)  # the first poll is answered idle; the Next now sleeps
    with pytest.raises(TimeoutError):
        session.dot_version(timeout=0.05)
    time.sleep(0.9)
    assert b"Y" not in nxt.commands
    nxt.drop()


def test_reply_longer_than_255_bytes_is_received(listener):
    long_version = "5.9.14" + "x" * 400
    nxt = FakeNext(listener.port, version=long_version)
    nxt.connect()
    session = listener.wait_session(timeout=2)
    assert session.dot_version(timeout=2) == long_version
    nxt.drop()


@pytest.mark.parametrize("reply", [b"O", b"", b"Osync\x00\xff\xfe"])
def test_malformed_ident_reply_gives_unknown_version(listener, reply):
    nxt = FakeNext(listener.port, ident_payload=reply)
    nxt.connect()
    session = listener.wait_session(timeout=2)
    assert session.dot_version(timeout=2) is None
    assert not session.wait_closed(timeout=0.2)
    nxt.drop()


def test_reply_with_bad_checksum_is_resent_by_the_next(listener):
    nxt = FakeNext(listener.port, version="5.9.14", corrupt_replies=2)
    nxt.connect()
    session = listener.wait_session(timeout=2)
    assert session.dot_version(timeout=2) == "5.9.14"
    assert nxt.resends == 2
    nxt.drop()


@pytest.mark.parametrize("total", [2, 4097])
def test_reply_with_impossible_length_ends_the_session(listener, total):
    nxt = FakeNext(listener.port, bad_header_total=total)
    nxt.connect()
    session = listener.wait_session(timeout=2)
    with pytest.raises(ConnectionError):
        session.dot_version(timeout=2)
    assert session.wait_closed(timeout=2)


def _session_with(listener, **fake_kwargs):
    nxt = FakeNext(listener.port, **fake_kwargs)
    nxt.connect()
    return nxt, listener.wait_session(timeout=2)


def test_list_dir_returns_folders_and_files_with_sizes(listener):
    nxt, session = _session_with(
        listener,
        fs={
            "c:/games": None,
            "c:/games/manic.tap": b"x" * 300,
            "c:/games/sub": None,
            "c:/readme.txt": b"hello",
            "m:/tmp.bin": b"zz",
        },
    )
    entries = session.list_dir("c:/games", timeout=2)
    assert sorted((e.name, e.is_dir, e.size) for e in entries) == [
        ("manic.tap", False, 300),
        ("sub", True, 0),
    ]
    nxt.drop()


def test_list_dir_of_a_large_folder_returns_every_entry(listener):
    files = {f"c:/big/file-number-{i:04d}.tap": b"x" * i for i in range(150)}
    nxt, session = _session_with(listener, fs={"c:/big": None, **files})
    entries = session.list_dir("c:/big", timeout=5)
    assert sorted((e.name, e.size) for e in entries) == sorted(
        (path.rsplit("/", 1)[1], len(data)) for path, data in files.items()
    )
    assert nxt.max_listing_block <= 1001  # the dot starts a new D block past 1000 bytes
    nxt.drop()


def test_list_dir_of_a_missing_folder_fails_and_the_session_stays_usable(listener):
    nxt, session = _session_with(listener, fs={"c:/a.txt": b"1"})
    with pytest.raises(RemoteError):
        session.list_dir("c:/nope", timeout=2)
    assert [e.name for e in session.list_dir("c:/", timeout=2)] == ["a.txt"]
    nxt.drop()


def test_list_dir_of_an_empty_folder_is_empty(listener):
    nxt, session = _session_with(listener, fs={"c:/empty": None})
    assert session.list_dir("c:/empty", timeout=2) == []
    nxt.drop()


def test_drives_reports_current_drive_and_letters(listener):
    nxt, session = _session_with(listener, drives="CM", current_drive="C")
    info = session.drives(timeout=2)
    assert info.current == "C"
    assert info.letters == ["C", "M"]
    nxt.drop()


def test_free_space_is_in_bytes_for_a_given_drive(listener):
    nxt, session = _session_with(listener, free_blocks={"C": 2048, "M": 10})
    assert session.free_space("C", timeout=2) == 2048 * 512
    assert session.free_space("M", timeout=2) == 10 * 512
    nxt.drop()


def test_free_space_of_an_unmeasurable_drive_fails(listener):
    nxt, session = _session_with(listener, free_blocks={"C": 1})
    with pytest.raises(RemoteError):
        session.free_space("M", timeout=2)
    nxt.drop()



def test_list_dir_refuses_a_path_over_254_bytes_without_sending_it(listener):
    longest_ok = "c:/" + "a" * 251  # 254 bytes
    nxt, session = _session_with(listener, fs={longest_ok: None})
    too_long = "c:/" + "a" * 252  # 255 bytes: the dot would truncate it silently
    with pytest.raises(RemoteError):
        session.list_dir(too_long, timeout=2)
    assert nxt.listed == []
    assert session.list_dir(longest_ok, timeout=2) == []  # 254 bytes still goes out
    assert len(nxt.listed) == 1
    nxt.drop()


def test_list_dir_refuses_a_non_ascii_path_without_sending_it(listener):
    nxt, session = _session_with(listener, fs={"c:/a": None})
    with pytest.raises(RemoteError):
        session.list_dir("c:/café", timeout=2)
    assert nxt.listed == []
    nxt.drop()


def test_put_file_stores_the_content_on_the_next(listener, tmp_path):
    local = tmp_path / "game.tap"
    content = bytes(range(256)) * 5  # 1280 bytes: several 512-byte chunks, packetno wraps nowhere
    local.write_bytes(content)
    nxt, session = _session_with(listener, drives="CDM", fs={"d:/games": None})
    session.put_file(str(local), "d:/games/game.tap", timeout=5)
    assert nxt.fs["d:/games/game.tap"] == content
    nxt.drop()


def test_failed_put_raises_leaves_the_partial_file_and_the_session_stays_usable(listener, tmp_path):
    local = tmp_path / "big.bin"
    local.write_bytes(b"x" * 2000)
    nxt, session = _session_with(listener, drives="CDM", truncate_puts_to=600)
    with pytest.raises(RemoteError):
        session.put_file(str(local), "d:/big.bin", timeout=5)
    assert nxt.fs["d:/big.bin"] == b"x" * 600  # nothing is deleted on the Next
    assert session.dot_version(timeout=2) == "5.9.14"
    nxt.drop()


def test_get_file_writes_the_content_of_the_next_file_locally(listener, tmp_path):
    content = bytes(range(256)) * 9  # 2304 bytes: several D blocks
    nxt, session = _session_with(listener, drives="CDM", fs={"d:/games/game.tap": content})
    target = tmp_path / "copy.tap"
    session.get_file("d:/games/game.tap", str(target), timeout=5)
    assert target.read_bytes() == content
    nxt.drop()


def test_get_file_of_a_missing_path_fails_and_writes_nothing(listener, tmp_path):
    nxt, session = _session_with(listener, drives="CDM", fs={"d:/a.txt": b"1"})
    target = tmp_path / "x.txt"
    with pytest.raises(RemoteError):
        session.get_file("d:/nope.txt", str(target), timeout=5)
    assert not target.exists()
    assert session.dot_version(timeout=2) == "5.9.14"
    nxt.drop()


def test_put_survives_a_chunk_the_next_asks_to_have_resent(listener, tmp_path):
    local = tmp_path / "a.bin"
    content = bytes(range(256)) * 6
    local.write_bytes(content)
    nxt, session = _session_with(listener, drives="CDM", put_retry_chunks=frozenset({1}))
    session.put_file(str(local), "d:/a.bin", timeout=5)
    assert nxt.fs["d:/a.bin"] == content
    assert nxt.retries_sent == 1
    nxt.drop()


def test_put_survives_a_restart_asked_by_the_next(listener, tmp_path):
    local = tmp_path / "a.bin"
    content = bytes(range(256)) * 6
    local.write_bytes(content)
    nxt, session = _session_with(listener, drives="CDM", put_restart_at_chunk=2)
    session.put_file(str(local), "d:/a.bin", timeout=5)
    assert nxt.fs["d:/a.bin"] == content
    nxt.drop()


def test_a_put_slower_than_the_timeout_succeeds_while_it_keeps_progressing(listener, tmp_path):
    local = tmp_path / "slow.bin"
    content = b"s" * (512 * 8)
    local.write_bytes(content)
    nxt, session = _session_with(listener, drives="CDM", put_chunk_delay=0.1)  # ~1 s in all
    session.put_file(str(local), "d:/slow.bin", timeout=0.4)
    assert nxt.fs["d:/slow.bin"] == content
    nxt.drop()


def test_a_put_that_stalls_times_out_and_ends_the_session_instead_of_leaving_it_serving(listener, tmp_path):
    local = tmp_path / "stuck.bin"
    local.write_bytes(b"x" * 2000)
    nxt, session = _session_with(listener, drives="CDM", put_stalls_at_chunk=2)
    with pytest.raises(TimeoutError):
        session.put_file(str(local), "d:/stuck.bin", timeout=0.3)
    assert session.wait_closed(timeout=2)  # out of step with the Next: nothing may go on
    with pytest.raises(ConnectionError):
        session.dot_version(timeout=1)
    nxt.drop()


@pytest.mark.parametrize("hook", ["progress", "cancel"])
def test_a_failing_put_callback_reaches_the_caller_at_once_and_the_session_stays_usable(listener, tmp_path, hook):
    local = tmp_path / "a.bin"
    local.write_bytes(b"x" * 2000)
    nxt, session = _session_with(listener, drives="CDM")

    def boom(*_):
        raise ValueError("callback broke")

    started = time.monotonic()
    with pytest.raises(ValueError, match="callback broke"):
        session.put_file(str(local), "d:/a.bin", timeout=5, **{hook: boom})
    assert time.monotonic() - started < 2  # not the full timeout
    assert session.dot_version(timeout=2) == "5.9.14"
    nxt.drop()


def test_a_get_cut_short_leaves_no_partial_file_and_keeps_the_previous_one(listener, tmp_path):
    nxt, session = _session_with(
        listener, drives="CDM", fs={"d:/big.bin": b"n" * 4000}, get_drops_after_blocks=2
    )
    target = tmp_path / "big.bin"
    target.write_bytes(b"old content")
    with pytest.raises(ConnectionError):
        session.get_file("d:/big.bin", str(target), timeout=5)
    assert target.read_bytes() == b"old content"
    assert [p.name for p in tmp_path.iterdir()] == ["big.bin"]  # no partial file either


def test_the_wire_trace_records_what_is_sent_and_received_when_asked(listener, tmp_path, monkeypatch):
    trace = tmp_path / "wire.log"
    monkeypatch.setenv("NEXPLORER_TRACE", str(trace))
    nxt, session = _session_with(listener, drives="CDM")
    assert session.dot_version(timeout=2) == "5.9.14"
    nxt.drop()
    session.wait_closed(timeout=2)
    lines = trace.read_text().splitlines()
    assert any(l.endswith(" rx 1 50") for l in lines)  # the "P" of a Poll
    assert any(" tx " in l for l in lines)
    assert any(" end " in l for l in lines)  # the Session ended: when, and how


def test_without_the_trace_variable_nothing_is_written(listener, tmp_path, monkeypatch):
    monkeypatch.delenv("NEXPLORER_TRACE", raising=False)
    monkeypatch.chdir(tmp_path)
    nxt, session = _session_with(listener, drives="CDM")
    session.dot_version(timeout=2)
    nxt.drop()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("path", ["d:/Download/../Download/a.bin", "d:/./a.bin", "d:/x/.."])
def test_a_path_with_a_dot_or_dotdot_component_is_refused_without_being_sent(listener, tmp_path, path):
    local = tmp_path / "a.bin"
    local.write_bytes(b"x")
    nxt, session = _session_with(listener, drives="CDM", fs={"d:/Download": None})
    with pytest.raises(RemoteError):
        session.put_file(str(local), path, timeout=2)
    with pytest.raises(RemoteError):
        session.list_dir(path, timeout=2)
    time.sleep(0.1)
    assert b"P" not in nxt.commands and b"L" not in nxt.commands
    nxt.drop()


def test_get_file_reports_the_bytes_received_so_far(listener, tmp_path):
    content = bytes(range(256)) * 9  # 2304 bytes: three D blocks of up to 1024
    nxt, session = _session_with(listener, drives="CDM", fs={"d:/a.bin": content})
    seen = []
    session.get_file("d:/a.bin", str(tmp_path / "a.bin"), timeout=5, progress=seen.append)
    assert seen == [1024, 2048, 2304]
    assert (tmp_path / "a.bin").read_bytes() == content
    nxt.drop()


def test_list_dir_never_returns_dot_and_dotdot_entries(listener):
    nxt, session = _session_with(
        listener,
        drives="CDM",
        fs={"d:/dl": None, "d:/dl/.": None, "d:/dl/..": None, "d:/dl/a.tap": b"1"},
    )
    assert [e.name for e in session.list_dir("d:/dl", timeout=2)] == ["a.tap"]
    nxt.drop()


def test_ending_the_session_makes_the_next_leave_and_waits_for_it(listener):
    nxt, session = _session_with(listener, drives="CDM")
    assert listener.end_session(timeout=3) is True
    assert nxt.ended.wait(timeout=2)
    assert listener.current_session is None


def test_ending_the_session_without_one_returns_at_once(listener):
    assert listener.end_session(timeout=3) is True


def _session_with(listener, **kwargs):
    nxt = FakeNext(listener.port, **kwargs)
    nxt.connect()
    return nxt, listener.wait_session(timeout=2)


def test_rename_moves_a_file_and_a_folder_in_place(listener):
    nxt, session = _session_with(
        listener, fs={"d:/games": None, "d:/games/a.tap": b"x", "d:/note.txt": b"hi"}
    )
    session.rename("d:/note.txt", "d:/readme.txt", timeout=2)
    session.rename("d:/games", "d:/arcade", timeout=2)
    assert nxt.fs == {"d:/arcade": None, "d:/arcade/a.tap": b"x", "d:/readme.txt": b"hi"}
    nxt.drop()


def test_rename_onto_an_existing_name_or_a_missing_source_fails(listener):
    nxt, session = _session_with(listener, fs={"d:/a": b"1", "d:/b": b"2"})
    with pytest.raises(RemoteError):
        session.rename("d:/a", "d:/b", timeout=2)
    with pytest.raises(RemoteError):
        session.rename("d:/nope", "d:/c", timeout=2)
    assert nxt.fs == {"d:/a": b"1", "d:/b": b"2"}
    nxt.drop()


def test_rename_refuses_dot_components_and_never_sends_them(listener):
    nxt, session = _session_with(listener, fs={"d:/a": b"1"})
    with pytest.raises(RemoteError):
        session.rename("d:/a", "d:/../b", timeout=2)
    assert b"V" not in nxt.commands
    nxt.drop()


def test_remove_file_deletes_a_file_and_fails_on_a_missing_one(listener):
    nxt, session = _session_with(listener, fs={"d:/a": b"1", "d:/b": b"2"})
    session.remove_file("d:/a", timeout=2)
    assert nxt.fs == {"d:/b": b"2"}
    with pytest.raises(RemoteError):
        session.remove_file("d:/a", timeout=2)
    nxt.drop()


def test_remove_dir_deletes_an_empty_folder_only(listener):
    nxt, session = _session_with(
        listener, fs={"d:/empty": None, "d:/full": None, "d:/full/x": b"1"}
    )
    session.remove_dir("d:/empty", timeout=2)
    with pytest.raises(RemoteError):
        session.remove_dir("d:/full", timeout=2)
    assert nxt.fs == {"d:/full": None, "d:/full/x": b"1"}
    nxt.drop()


def test_copy_duplicates_a_file_across_drives_and_keeps_the_source(listener):
    nxt, session = _session_with(listener, fs={"c:/a.tap": b"tape"})
    session.copy("c:/a.tap", "m:/b.tap", timeout=2)
    assert nxt.fs == {"c:/a.tap": b"tape", "m:/b.tap": b"tape"}
    nxt.drop()


def test_copy_of_a_folder_copies_the_whole_tree_and_merges_into_an_existing_one(listener):
    nxt, session = _session_with(
        listener,
        fs={"c:/g": None, "c:/g/one": b"1", "c:/g/s": None, "c:/g/s/two": b"2", "m:/g": None, "m:/g/old": b"o"},
    )
    session.copy("c:/g", "m:/g", timeout=2)
    assert nxt.fs["m:/g/one"] == b"1" and nxt.fs["m:/g/s/two"] == b"2" and nxt.fs["m:/g/old"] == b"o"
    assert nxt.fs["c:/g/one"] == b"1"
    nxt.drop()


def test_copy_refuses_a_destination_inside_the_source_without_sending_it(listener):
    nxt, session = _session_with(listener, fs={"c:/g": None, "c:/g/one": b"1"})
    for dest in ("c:/g/inner", "C:/G", "c:/g/"):
        with pytest.raises(RemoteError):
            session.copy("c:/g", dest, timeout=2)
    assert b"C" not in nxt.commands
    nxt.drop()


def test_a_failing_copy_raises_and_leaves_the_files_already_copied(listener):
    nxt, session = _session_with(
        listener,
        fs={"c:/g": None, "c:/g/a": b"1", "c:/g/b": b"2", "c:/g/c": b"3"},
        copy_fails_after=1,
    )
    with pytest.raises(RemoteError):
        session.copy("c:/g", "m:/g", timeout=2)
    copied = [k for k in nxt.fs if k.startswith("m:/g/")]
    assert len(copied) == 1  # copied files stay, like an interrupted cp
    nxt.drop()


def test_copy_on_a_dot_that_ignores_the_opcode_raises_instead_of_crashing(listener):
    nxt, session = _session_with(listener, fs={"c:/a": b"1"}, ignores=frozenset({b"C"}))
    with pytest.raises(RemoteError):
        session.copy("c:/a", "m:/a", timeout=2)
    nxt.drop()

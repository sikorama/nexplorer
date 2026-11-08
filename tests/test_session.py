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

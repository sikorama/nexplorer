import time

import pytest

from nexplorer.protocol import Listener
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

import pytest

from nexplorer.protocol import Listener
from nexplorer.ui.panes import NextBackend
from tests.fake_next import FakeNext


@pytest.fixture
def listener():
    l = Listener(host="127.0.0.1", port=0)
    l.start()
    yield l
    l.stop()


def test_the_next_listing_hides_dot_and_dotdot_entries(listener):
    nxt = FakeNext(
        listener.port,
        drives="CDM",
        fs={"d:/dl": None, "d:/dl/.": None, "d:/dl/..": None, "d:/dl/a.tap": b"1"},
    )
    nxt.connect()
    backend = NextBackend()
    backend.session = listener.wait_session(timeout=2)
    backend.allowed_drives = {"D"}

    assert [e.name for e in backend.list("d:/dl")] == ["a.tap"]
    nxt.drop()


def test_joining_dotdot_goes_to_the_parent_folder_and_dot_stays_put():
    backend = NextBackend()
    assert backend.join("d:/Download", "..") == "d:/"
    assert backend.join("d:/a/b", "..") == "d:/a"
    assert backend.join("d:/a/b", ".") == "d:/a/b"
    assert backend.join("d:/a", "b") == "d:/a/b"

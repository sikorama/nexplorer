import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from nexplorer.protocol import Listener
from nexplorer.ui.main_window import MainWindow
from tests.conftest import dispose, pump
from tests.fake_next import FakeNext

FS = {
    "c:/dest": None,
    "c:/dest/a.txt": b"old-a",
    "c:/dest/b.txt": b"old-b",
    "c:/dest/sub": None,
    "c:/dest/sub/x.txt": b"old-x",
    "c:/dest/sub/keep.txt": b"keep",
}


class Answers:
    """Scripted overwrite prompt: answers in order, then repeats the last."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.asked = []

    def __call__(self, path, remaining):
        self.asked.append((path, remaining))
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


@pytest.fixture
def setup(app, tmp_path):
    listener = Listener(host="127.0.0.1", port=0)
    listener.start()
    made = []

    def build(*answers):
        prompt = Answers(*answers or [("cancel", False)])
        w = MainWindow(listener, local_addresses=lambda: [], confirm_overwrite=prompt)
        made.append(w)
        w.show()
        nxt = FakeNext(listener.port, fs=dict(FS), free_blocks={"C": 2048})
        nxt.connect()
        assert pump(app, lambda: w.next_pane_state() == "connected")
        assert pump(app, lambda: w.next_pane().path() == "c:/" and "dest" in w.next_pane().names())
        w.next_pane().enter("dest")
        assert pump(app, lambda: w.next_pane().path() == "c:/dest" and "a.txt" in w.next_pane().names())
        w.local_pane().go_to(str(tmp_path))
        assert pump(app, lambda: w.local_pane().path() == str(tmp_path))
        return w, nxt, prompt

    yield build, tmp_path
    for w in made:
        w.close()
        dispose(app, w)
    listener.stop()


def run_and_wait(app, w, action):
    action()
    assert pump(app, lambda: w.operation_running())
    assert pump(app, lambda: not w.operation_running(), timeout=10)


def local_files(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"new-a")
    (tmp_path / "b.txt").write_bytes(b"new-b")
    (tmp_path / "c.txt").write_bytes(b"new-c")


def test_a_send_without_collision_asks_nothing(app, setup):
    build, tmp_path = setup
    w, nxt, prompt = build()
    (tmp_path / "fresh.txt").write_bytes(b"f")
    run_and_wait(app, w, lambda: w.drop_files([str(tmp_path / "fresh.txt")]))
    assert prompt.asked == []
    assert nxt.fs["c:/dest/fresh.txt"] == b"f"


def test_overwrite_replaces_the_existing_file(app, setup):
    build, tmp_path = setup
    w, nxt, prompt = build(("overwrite", False))
    local_files(tmp_path)
    run_and_wait(app, w, lambda: w.drop_files([str(tmp_path / "a.txt")]))
    assert prompt.asked == [("c:/dest/a.txt", 1)]
    assert nxt.fs["c:/dest/a.txt"] == b"new-a"


def test_skip_leaves_the_colliding_file_and_sends_the_rest(app, setup):
    build, tmp_path = setup
    w, nxt, prompt = build(("skip", False))
    local_files(tmp_path)
    run_and_wait(app, w, lambda: w.drop_files([str(tmp_path / "a.txt"), str(tmp_path / "c.txt")]))
    assert nxt.fs["c:/dest/a.txt"] == b"old-a"
    assert nxt.fs["c:/dest/c.txt"] == b"new-c"
    assert w.summary_text().startswith("Done")


def test_cancel_stops_the_whole_batch(app, setup):
    build, tmp_path = setup
    w, nxt, prompt = build(("cancel", False))
    local_files(tmp_path)
    w.drop_files([str(tmp_path / "a.txt"), str(tmp_path / "c.txt")])
    assert pump(app, lambda: prompt.asked and not w.operation_running())
    pump(app, lambda: False, timeout=0.3)
    assert nxt.fs["c:/dest/a.txt"] == b"old-a"
    assert "c:/dest/c.txt" not in nxt.fs
    assert w.summary_text() == "Cancelled"


def test_apply_to_all_answers_the_remaining_collisions(app, setup):
    build, tmp_path = setup
    w, nxt, prompt = build(("overwrite", True))
    local_files(tmp_path)
    run_and_wait(app, w, lambda: w.drop_files([str(tmp_path / n) for n in ("a.txt", "b.txt", "c.txt")]))
    assert len(prompt.asked) == 1 and prompt.asked[0][1] == 2
    assert nxt.fs["c:/dest/a.txt"] == b"new-a" and nxt.fs["c:/dest/b.txt"] == b"new-b"


def test_each_collision_can_get_its_own_answer(app, setup):
    build, tmp_path = setup
    w, nxt, prompt = build(("overwrite", False), ("skip", False))
    local_files(tmp_path)
    run_and_wait(app, w, lambda: w.drop_files([str(tmp_path / n) for n in ("a.txt", "b.txt")]))
    assert len(prompt.asked) == 2
    assert nxt.fs["c:/dest/a.txt"] == b"new-a" and nxt.fs["c:/dest/b.txt"] == b"old-b"


def test_a_folder_merging_into_an_existing_folder_asks_only_for_colliding_files(app, setup):
    build, tmp_path = setup
    w, nxt, prompt = build(("skip", False))
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "x.txt").write_bytes(b"new-x")
    (tmp_path / "sub" / "y.txt").write_bytes(b"new-y")
    run_and_wait(app, w, lambda: w.drop_files([str(tmp_path / "sub")]))
    assert [p for p, _ in prompt.asked] == ["c:/dest/sub/x.txt"]
    assert nxt.fs["c:/dest/sub/x.txt"] == b"old-x"
    assert nxt.fs["c:/dest/sub/y.txt"] == b"new-y"
    assert nxt.fs["c:/dest/sub/keep.txt"] == b"keep"


def test_a_name_differing_only_by_case_collides_on_the_next(app, setup):
    build, tmp_path = setup
    w, nxt, prompt = build(("skip", False))
    (tmp_path / "A.TXT").write_bytes(b"new")
    run_and_wait(app, w, lambda: w.drop_files([str(tmp_path / "A.TXT")]))
    assert [p for p, _ in prompt.asked] == ["c:/dest/A.TXT"]
    assert nxt.fs["c:/dest/a.txt"] == b"old-a"


def test_a_failing_destination_listing_refuses_the_batch_with_a_message(app, setup):
    build, tmp_path = setup
    w, nxt, prompt = build(("overwrite", True))
    local_files(tmp_path)
    del nxt.fs["c:/dest"]
    w.drop_files([str(tmp_path / "a.txt")])
    assert pump(app, lambda: not w.operation_running() and w.summary_text())
    assert "cannot be checked" in w.summary_text()
    assert prompt.asked == []
    assert nxt.fs["c:/dest/a.txt"] == b"old-a"  # never sent


def test_a_receive_onto_an_existing_name_asks_and_skip_keeps_the_local_file(app, setup):
    build, tmp_path = setup
    w, nxt, prompt = build(("skip", False))
    (tmp_path / "a.txt").write_bytes(b"mine")
    w.next_pane().select(["a.txt", "b.txt"])
    run_and_wait(app, w, w.receive_selected)
    assert [p for p, _ in prompt.asked] == [str(tmp_path / "a.txt")]
    assert (tmp_path / "a.txt").read_bytes() == b"mine"
    assert (tmp_path / "b.txt").read_bytes() == b"old-b"


def test_a_receive_with_overwrite_replaces_the_local_file(app, setup):
    build, tmp_path = setup
    w, nxt, prompt = build(("overwrite", False))
    (tmp_path / "a.txt").write_bytes(b"mine")
    w.next_pane().select(["a.txt"])
    run_and_wait(app, w, w.receive_selected)
    assert (tmp_path / "a.txt").read_bytes() == b"old-a"


def test_a_receive_cancelled_changes_nothing(app, setup):
    build, tmp_path = setup
    w, nxt, prompt = build(("cancel", False))
    (tmp_path / "a.txt").write_bytes(b"mine")
    w.next_pane().select(["a.txt", "b.txt"])
    w.receive_selected()
    assert pump(app, lambda: prompt.asked and not w.operation_running())
    pump(app, lambda: False, timeout=0.3)
    assert (tmp_path / "a.txt").read_bytes() == b"mine" and not (tmp_path / "b.txt").exists()


def test_a_send_from_the_selection_asks_too(app, setup):
    build, tmp_path = setup
    w, nxt, prompt = build(("skip", False))
    local_files(tmp_path)
    w.local_pane().reload()
    assert pump(app, lambda: "a.txt" in w.local_pane().names())
    w.local_pane().select(["a.txt"])
    run_and_wait(app, w, w.send_selected)
    assert [p for p, _ in prompt.asked] == ["c:/dest/a.txt"]


def test_copy_and_paste_inside_the_next_still_refuse_to_overwrite(app, setup):
    build, tmp_path = setup
    w, nxt, prompt = build()
    w.next_pane().select(["a.txt"])
    w.copy_selected()
    w.next_pane().enter("sub")
    assert pump(app, lambda: w.next_pane().path() == "c:/dest/sub")
    nxt.fs["c:/dest/sub/a.txt"] = b"there"
    w.next_pane().reload()
    assert pump(app, lambda: "a.txt" in w.next_pane().names())
    run_and_wait(app, w, w.paste)
    assert prompt.asked == []
    assert nxt.fs["c:/dest/sub/a.txt"] == b"there"
    assert "already exists" in w.summary_text()

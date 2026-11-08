from pathlib import Path

import pytest

from nexplorer.ui.panes import LocalPane
from tests.conftest import dispose, pump


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    (tmp_path / "games").mkdir()
    (tmp_path / "games" / "inner.tap").write_bytes(b"1")
    (tmp_path / "manic.tap").write_bytes(b"x" * 300)
    (tmp_path / "demo.nex").write_bytes(b"y" * 5000)
    return tmp_path


@pytest.fixture(autouse=True)
def panes(app):
    opened = []
    yield opened
    dispose(app, *opened)


@pytest.fixture
def open_pane(app, panes):
    def open_pane(app, path) -> LocalPane:
        pane = LocalPane(str(path))
        panes.append(pane)
        assert pump(app, lambda: not pane.is_loading() and pane.names() != [])
        return pane

    return open_pane


def test_lists_name_size_and_type_folders_first(app, folder, open_pane):
    pane = open_pane(app, folder)
    assert pane.rows() == [
        ("games", "", "Folder"),
        ("demo.nex", "4.9 KB", "NEX"),
        ("manic.tap", "300 B", "TAP"),
    ]


def settled(app, pane):
    assert pump(app, lambda: not pane.is_loading())


def test_enter_a_folder_then_go_up(app, folder, open_pane):
    pane = open_pane(app, folder)
    pane.enter("games")
    settled(app, pane)
    assert pane.path() == str(folder / "games")
    assert pane.names() == ["inner.tap"]
    pane.go_up()
    settled(app, pane)
    assert pane.path() == str(folder)
    assert "games" in pane.names()


def test_entering_a_file_does_nothing(app, folder, open_pane):
    pane = open_pane(app, folder)
    pane.enter("manic.tap")
    settled(app, pane)
    assert pane.path() == str(folder)


def test_typed_path_navigates(app, folder, open_pane):
    pane = open_pane(app, folder)
    pane.go_to(str(folder / "games"))
    settled(app, pane)
    assert pane.names() == ["inner.tap"]


def test_typed_path_that_does_not_exist_keeps_the_folder_and_reports_an_error(app, folder, open_pane):
    pane = open_pane(app, folder)
    pane.go_to(str(folder / "nope"))
    settled(app, pane)
    assert pane.path() == str(folder)
    assert "games" in pane.names()
    assert pane.error() != ""
    pane.go_to(str(folder / "games"))
    settled(app, pane)
    assert pane.error() == ""


def test_sorting_by_size_then_again_reverses_it(app, folder, open_pane):
    pane = open_pane(app, folder)
    pane.sort_by("size")
    assert pane.names() == ["games", "manic.tap", "demo.nex"]
    pane.sort_by("size")
    assert pane.names() == ["games", "demo.nex", "manic.tap"]
    pane.sort_by("type")
    assert pane.names() == ["games", "demo.nex", "manic.tap"]
    pane.sort_by("name")
    assert pane.names() == ["games", "demo.nex", "manic.tap"]


def test_several_entries_can_be_selected_at_once(app, folder, open_pane):
    pane = open_pane(app, folder)
    pane.select(["games", "manic.tap"])
    assert pane.selected_names() == ["games", "manic.tap"]
    pane.select(["demo.nex"])
    assert pane.selected_names() == ["demo.nex"]


def test_selection_is_cleared_when_the_folder_changes(app, folder, open_pane):
    pane = open_pane(app, folder)
    pane.select(["games"])
    pane.enter("games")
    settled(app, pane)
    assert pane.selected_names() == []

from nexplorer.listing import sort_entries
from nexplorer.protocol import Entry


def names(entries):
    return [e.name for e in entries]


ENTRIES = [
    Entry("b.tap", False, 30),
    Entry("zdir", True, 0),
    Entry("A.nex", False, 500),
    Entry("adir", True, 0),
    Entry("c.TAP", False, 10),
]


def test_sort_by_name_ignores_case_and_keeps_folders_first():
    assert names(sort_entries(ENTRIES, "name")) == ["adir", "zdir", "A.nex", "b.tap", "c.TAP"]


def test_sort_by_size_puts_folders_first_then_smallest_file_first():
    assert names(sort_entries(ENTRIES, "size")) == ["adir", "zdir", "c.TAP", "b.tap", "A.nex"]


def test_sort_by_type_groups_by_extension_ignoring_case_then_name():
    assert names(sort_entries(ENTRIES, "type")) == ["adir", "zdir", "A.nex", "b.tap", "c.TAP"]


def test_descending_reverses_files_but_folders_stay_first():
    assert names(sort_entries(ENTRIES, "size", descending=True)) == [
        "zdir", "adir", "A.nex", "b.tap", "c.TAP",
    ]

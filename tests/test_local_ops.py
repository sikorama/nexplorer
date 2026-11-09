"""Local operations on a temporary directory, with an injected trash."""
import os

from nexplorer import local_ops


class Trash:
    """A fake trash: records the paths, optionally fails, really removes the rest."""

    def __init__(self, fail=()):
        self.paths, self.fail = [], set(fail)

    def __call__(self, path):
        if os.path.basename(path) in self.fail:
            raise OSError("no trash here")
        self.paths.append(path)
        local_ops.delete_path(path)


def tree(root):
    out = {}
    for base, dirs, files in os.walk(root):
        for d in dirs:
            out[os.path.relpath(os.path.join(base, d), root)] = None
        for f in files:
            p = os.path.join(base, f)
            with open(p, "rb") as handle:
                out[os.path.relpath(p, root)] = handle.read()
    return out


def test_make_folder_creates_it_and_refuses_existing_or_unsafe_names(tmp_path):
    assert local_ops.make_folder(str(tmp_path), "saves").failures == []
    assert (tmp_path / "saves").is_dir()
    assert [f.name for f in local_ops.make_folder(str(tmp_path), "saves").failures] == ["saves"]
    for bad in ("", ".", "..", "a/b", "a\\b", "c:x"):
        assert [f.name for f in local_ops.make_folder(str(tmp_path), bad).failures] == [bad]
    assert sorted(os.listdir(tmp_path)) == ["saves"]


def test_rename_renames_and_never_replaces_another_entry(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"a")
    (tmp_path / "b.txt").write_bytes(b"b")
    assert local_ops.rename(str(tmp_path), "a.txt", "c.txt").failures == []
    assert (tmp_path / "c.txt").read_bytes() == b"a"
    assert [f.name for f in local_ops.rename(str(tmp_path), "c.txt", "b.txt").failures] == ["c.txt"]
    assert (tmp_path / "b.txt").read_bytes() == b"b" and (tmp_path / "c.txt").exists()
    assert local_ops.rename(str(tmp_path), "c.txt", "../x").failures
    assert not (tmp_path.parent / "x").exists()


def test_trash_sends_each_entry_to_the_trash_and_reports_the_ones_that_fail(tmp_path):
    for name in ("a", "b", "c"):
        (tmp_path / name).write_bytes(b"x")
    trash = Trash(fail={"b"})
    result = local_ops.trash_entries(str(tmp_path), ["a", "b", "c"], trash)
    assert [f.name for f in result.failures] == ["b"]
    assert "no trash here" in result.failures[0].reason
    assert sorted(os.listdir(tmp_path)) == ["b"]


def test_delete_permanently_removes_files_and_folders_with_their_content(tmp_path):
    (tmp_path / "d" / "e").mkdir(parents=True)
    (tmp_path / "d" / "e" / "f").write_bytes(b"x")
    (tmp_path / "g").write_bytes(b"x")
    assert [f.name for f in local_ops.delete_entries(str(tmp_path), ["d", "g", "ghost"]).failures] == ["ghost"]
    assert os.listdir(tmp_path) == []


def test_move_into_a_folder_moves_files_and_folders(tmp_path):
    (tmp_path / "dest").mkdir()
    (tmp_path / "f.txt").write_bytes(b"f")
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "in.txt").write_bytes(b"i")
    result = local_ops.move(str(tmp_path), ["f.txt", "d"], str(tmp_path / "dest"))
    assert result.failures == [] and not result.cancelled
    assert tree(tmp_path) == {"dest": None, "dest/f.txt": b"f", "dest/d": None, "dest/d/in.txt": b"i"}


def test_copy_duplicates_and_keeps_the_source(tmp_path):
    (tmp_path / "dest").mkdir()
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "in.txt").write_bytes(b"i")
    (tmp_path / "f.txt").write_bytes(b"f")
    assert local_ops.copy(str(tmp_path), ["f.txt", "d"], str(tmp_path / "dest")).failures == []
    assert tree(tmp_path / "dest") == {"f.txt": b"f", "d": None, "d/in.txt": b"i"}
    assert (tmp_path / "f.txt").exists() and (tmp_path / "d" / "in.txt").exists()


def make_merge_case(root):
    (root / "src" / "sub").mkdir(parents=True)
    (root / "src" / "new.txt").write_bytes(b"new")
    (root / "src" / "same.txt").write_bytes(b"from src")
    (root / "src" / "sub" / "deep.txt").write_bytes(b"deep")
    (root / "dest" / "src" / "sub").mkdir(parents=True)
    (root / "dest" / "src" / "same.txt").write_bytes(b"kept")


def test_copying_a_folder_merges_and_refuses_an_existing_file(tmp_path):
    make_merge_case(tmp_path)
    result = local_ops.copy(str(tmp_path), ["src"], str(tmp_path / "dest"))
    assert [f.name for f in result.failures] == ["src/same.txt"]
    got = tree(tmp_path / "dest")
    assert got["src/same.txt"] == b"kept"
    assert got["src/new.txt"] == b"new" and got["src/sub/deep.txt"] == b"deep"
    assert (tmp_path / "src" / "same.txt").read_bytes() == b"from src"


def test_moving_a_folder_merges_and_keeps_the_refused_file_at_the_source(tmp_path):
    make_merge_case(tmp_path)
    result = local_ops.move(str(tmp_path), ["src"], str(tmp_path / "dest"))
    assert [f.name for f in result.failures] == ["src/same.txt"]
    got = tree(tmp_path / "dest")
    assert got["src/same.txt"] == b"kept"
    assert got["src/new.txt"] == b"new" and got["src/sub/deep.txt"] == b"deep"
    assert tree(tmp_path / "src") == {"same.txt": b"from src"}


def test_a_file_where_a_folder_is_expected_is_refused(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "dest").mkdir()
    (tmp_path / "dest" / "a").write_bytes(b"file")
    assert [f.name for f in local_ops.move(str(tmp_path), ["a"], str(tmp_path / "dest")).failures] == ["a"]
    assert (tmp_path / "a").is_dir() and (tmp_path / "dest" / "a").read_bytes() == b"file"


def test_into_the_same_folder_or_into_itself_is_refused(tmp_path):
    (tmp_path / "d" / "sub").mkdir(parents=True)
    for operation in (local_ops.copy, local_ops.move):
        assert [f.name for f in operation(str(tmp_path), ["d"], str(tmp_path)).failures] == ["d"]
        assert [f.name for f in operation(str(tmp_path), ["d"], str(tmp_path / "d" / "sub")).failures] == ["d"]
    assert tree(tmp_path) == {"d": None, "d/sub": None}


def test_a_missing_source_is_one_failure_and_the_others_still_go(tmp_path):
    (tmp_path / "dest").mkdir()
    (tmp_path / "ok").write_bytes(b"x")
    result = local_ops.move(str(tmp_path), ["ghost", "ok"], str(tmp_path / "dest"))
    assert [f.name for f in result.failures] == ["ghost"]
    assert (tmp_path / "dest" / "ok").exists()


def test_cancel_stops_before_the_next_entry_and_progress_is_reported(tmp_path):
    (tmp_path / "dest").mkdir()
    for name in ("a", "b", "c"):
        (tmp_path / name).write_bytes(b"x")
    seen, calls = [], []

    def cancel():
        calls.append(1)
        return len(calls) > 1

    result = local_ops.copy(
        str(tmp_path), ["a", "b", "c"], str(tmp_path / "dest"), lambda n, p: seen.append((n, p)), cancel
    )
    assert result.cancelled and os.listdir(tmp_path / "dest") == ["a"]
    assert seen and seen[0][0] == "a"

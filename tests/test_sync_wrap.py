"""Finding the shipped sync-wrap.bas: in a PyInstaller bundle, or in the source tree."""
import sys

from nexplorer import sync_wrap


def test_from_the_sources_it_is_the_program_in_the_repository_folder():
    found = sync_wrap.locate()
    assert found is not None and found.name == "sync-wrap.bas" and found.parent.name == "sync-wrap"
    assert found.read_bytes().startswith(b"PLUS3DOS")


def test_in_a_bundle_it_is_read_from_the_bundle_data_folder(tmp_path, monkeypatch):
    (tmp_path / "sync-wrap").mkdir()
    (tmp_path / "sync-wrap" / "sync-wrap.bas").write_bytes(b"bundled")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert sync_wrap.locate().read_bytes() == b"bundled"


def test_a_bundle_without_the_program_finds_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert sync_wrap.locate() is None

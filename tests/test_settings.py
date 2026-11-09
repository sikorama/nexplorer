import json
from pathlib import Path

from nexplorer.settings import Settings, config_path, load, save


def test_missing_file_gives_defaults(tmp_path):
    s = load(tmp_path / "absent.json")
    assert s.language == "en"
    assert s.show_hidden is False
    assert s.crc_after_upload is False
    assert s.local_folder == "" and s.next_folder == ""


def test_saved_settings_come_back(tmp_path):
    path = tmp_path / "sub" / "settings.json"
    s = Settings(local_folder="/home/me/zx", next_folder="d:/games", language="fr",
                 show_hidden=True, crc_after_upload=True, geometry="AAEC",
                 local_sort=("size", True), next_sort=("type", False))
    save(s, path)
    assert load(path) == s
    assert json.loads(path.read_text(encoding="utf-8"))["language"] == "fr"  # plain JSON


def test_corrupt_or_foreign_content_is_ignored_key_by_key(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"language": "fr", "show_hidden": "yes", "local_sort": ["bogus", 1], "extra": 1}))
    s = load(path)
    assert s.language == "fr"
    assert s.show_hidden is False
    assert s.local_sort == ("name", False)
    path.write_text("not json")
    assert load(path) == Settings()


def test_config_folder_follows_the_platform():
    home = Path("/home/me")
    assert config_path("linux", {"XDG_CONFIG_HOME": "/cfg"}, home) == Path("/cfg/nexplorer/settings.json")
    assert config_path("linux", {}, home) == Path("/home/me/.config/nexplorer/settings.json")
    assert config_path("win32", {"APPDATA": "C:/Users/me/AppData/Roaming"}, home) == Path(
        "C:/Users/me/AppData/Roaming/nexplorer/settings.json")
    assert config_path("darwin", {}, home) == Path("/home/me/Library/Application Support/nexplorer/settings.json")


def test_a_malformed_geometry_or_an_unknown_language_falls_back_to_the_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"geometry": "abc", "language": "../x", "show_hidden": True}))
    s = load(path)
    assert s.geometry == "" and s.language == "en"
    assert s.show_hidden is True  # the other keys survive
    path.write_text(json.dumps({"geometry": "AAEC", "language": "fr"}))
    assert (load(path).geometry, load(path).language) == ("AAEC", "fr")


def test_splitter_widths_round_trip_and_bad_values_fall_back(tmp_path):
    path = tmp_path / "settings.json"
    save(Settings(splitter=(300, 700)), path)
    assert load(path).splitter == (300, 700)
    assert Settings().splitter == ()
    for bad in ([1], [1, 2, 3], [0, 5], ["a", 1], "x", [True, 5]):
        path.write_text(json.dumps({"splitter": bad, "language": "fr"}))
        assert load(path).splitter == () and load(path).language == "fr"

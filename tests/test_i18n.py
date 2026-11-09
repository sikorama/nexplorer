import json

from nexplorer import i18n


def test_unknown_or_english_key_falls_back_to_itself():
    i18n.set_language("en")
    assert i18n.tr("Waiting for a Next") == "Waiting for a Next"


def test_catalogue_translates_by_english_text(tmp_path):
    (tmp_path / "xx.json").write_text(json.dumps({"Local": "Lokal"}), encoding="utf-8")
    i18n.set_language("xx", catalogue_dir=tmp_path)
    try:
        assert i18n.tr("Local") == "Lokal"
        assert i18n.tr("Next") == "Next"  # missing entry falls back
    finally:
        i18n.set_language("en")


def test_shipped_catalogues_are_listed_and_french_translates():
    assert "en" in i18n.available_languages() and "fr" in i18n.available_languages()
    i18n.set_language("fr")
    try:
        assert i18n.tr("Quit") == "Quitter"
        assert i18n.tr("a text no catalogue knows") == "a text no catalogue knows"
    finally:
        i18n.set_language("en")


def test_every_shipped_catalogue_is_valid_json_of_strings():
    for code in i18n.available_languages():
        path = i18n._DEFAULT_DIR / f"{code}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            assert all(isinstance(k, str) and isinstance(v, str) for k, v in data.items())


def test_the_overwrite_prompt_strings_are_translated_in_french():
    i18n.set_language("fr")
    try:
        for text in (
            "Already exists",
            "already exists. Overwrite it?",
            "Overwrite",
            "Skip",
            "Apply to all",
            "Not started, the destination cannot be checked",
        ):
            assert i18n.tr(text) != text
    finally:
        i18n.set_language("en")

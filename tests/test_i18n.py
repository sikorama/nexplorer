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

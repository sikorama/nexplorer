import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "check_release_tag", Path(__file__).parent.parent / "packaging" / "check_release_tag.py"
)
check_release_tag = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_release_tag)


def test_matching_tag_and_version_pass():
    assert check_release_tag.check("v0.1.0", "0.1.0") == "0.1.0"


@pytest.mark.parametrize("tag", ["v0.2.0", "v0.1.1", "v1.1.0"])
def test_other_version_is_refused(tag):
    with pytest.raises(ValueError, match="0.1.0"):
        check_release_tag.check(tag, "0.1.0")


def test_missing_v_prefix_is_refused():
    with pytest.raises(ValueError, match="vX.Y.Z"):
        check_release_tag.check("0.1.0", "0.1.0")


@pytest.mark.parametrize("tag", ["", "v", "v1", "v1.2", "v1.2.3.4", "vx.y.z", "v1.2.3-rc1", "refs/tags/v0.1.0"])
def test_malformed_tag_is_refused(tag):
    with pytest.raises(ValueError, match="vX.Y.Z"):
        check_release_tag.check(tag, "0.1.0")

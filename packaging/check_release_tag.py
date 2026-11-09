"""Refuses a release whose tag differs from the project version.

Usage: check_release_tag.py TAG   (reads the version from pyproject.toml)
Prints the version on success; exits 1 with a message otherwise.
"""
import re
import sys
import tomllib
from pathlib import Path

_TAG = re.compile(r"v(\d+\.\d+\.\d+)")


def check(tag: str, version: str) -> str:
    """Returns the version if `tag` is `v` + `version`, raises ValueError otherwise."""
    match = _TAG.fullmatch(tag)
    if not match:
        raise ValueError(f"Release tag {tag!r} is malformed; expected vX.Y.Z (for example v{version})")
    if match.group(1) != version:
        raise ValueError(
            f"Release tag {tag!r} does not match the project version {version!r} "
            f"in pyproject.toml; expected v{version}"
        )
    return version


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    project_version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    try:
        print(check(sys.argv[1], project_version))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

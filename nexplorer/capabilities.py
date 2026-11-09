"""What the dot can do, from the version it announces (docs/protocol.md, feature table)."""

import re
from dataclasses import dataclass

MINIMUM_DOT = "5.9.2"  # carries every feature the application uses

_COPY_SINCE = (5, 2)
_FREE_SPACE_SINCE = (5, 2)
_CRC_SINCE = (5, 9, 2)
# Rename (`V`) has no recorded first version: it is never refused on the version.


@dataclass(frozen=True)
class Capabilities:
    rename: bool = True
    copy: bool = True
    crc: bool = True
    free_space: bool = True

    @property
    def complete(self) -> bool:
        return self.rename and self.copy and self.crc and self.free_space


def _parse(version: str) -> tuple[int, ...] | None:
    if not re.fullmatch(r"\d+(\.\d+)*", version):
        return None
    return tuple(int(part) for part in version.split("."))


def capabilities(version: str | None) -> Capabilities:
    """What a dot announcing `version` supports. None means the dot did not answer `Y`
    (older than 5.8.0). Only what is provably missing is refused: an unparseable
    version refuses nothing."""
    if version is None:
        return Capabilities(crc=False)
    parsed = _parse(version)
    if parsed is None:
        return Capabilities()
    return Capabilities(
        copy=parsed >= _COPY_SINCE,
        crc=parsed >= _CRC_SINCE,
        free_space=parsed >= _FREE_SPACE_SINCE,
    )

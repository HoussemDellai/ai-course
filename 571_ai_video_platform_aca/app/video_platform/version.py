"""Single source of truth for the semantic version; Terraform reads the same VERSION file for the image tag."""
from __future__ import annotations

import re
from pathlib import Path

VERSION_FILE = Path(__file__).with_name("VERSION")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$")


def read_version() -> str:
    value = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not SEMVER.match(value):
        raise ValueError(f"{VERSION_FILE} must contain a semantic version such as 1.0.0, not {value!r}")
    return value


__version__ = read_version()

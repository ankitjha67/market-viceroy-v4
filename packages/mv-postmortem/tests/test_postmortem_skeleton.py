"""Phase-0 skeleton test: the package imports and exposes a version."""

from __future__ import annotations

import mv.postmortem as pkg


def test_version_exposed() -> None:
    assert pkg.__version__ == "0.0.1"

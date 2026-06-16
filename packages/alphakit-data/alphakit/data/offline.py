"""Offline mode for AlphaKit data feeds.

When ``ALPHAKIT_OFFLINE=1`` is set, feed adapters must not make network
calls. They route instead to the deterministic fixture generator in
:mod:`alphakit.data.fixtures.generator`, so test suites, CI jobs and
notebook runs can proceed without credentials or connectivity.

Two things ship here:

* :func:`is_offline` — one-line env-var check, used by every adapter.
* :func:`offline_fixture` — returns a fixture price panel shaped like
  the live ``fetch`` output, so adapters can substitute it without
  reshaping their callers' expectations.

:func:`offline_fallback` is a test helper: a context manager that
temporarily sets ``ALPHAKIT_OFFLINE=1`` inside a ``with`` block. It
restores the previous value (or unsets the variable) on exit so tests
never leak state.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

import pandas as pd
from alphakit.data.fixtures.generator import generate_fixture_prices


def is_offline() -> bool:
    """``True`` when ``ALPHAKIT_OFFLINE=1`` is set in the environment."""
    return os.environ.get("ALPHAKIT_OFFLINE", "").strip() == "1"


def offline_fixture(
    symbols: list[str],
    start: datetime | str,
    end: datetime | str,
    frequency: str = "1d",
) -> pd.DataFrame:
    """Return a deterministic fixture price panel.

    Shape matches what a live adjusted-close ``fetch`` call returns:
    a DataFrame indexed by business day with one column per symbol.
    ``frequency`` is accepted for signature parity but ignored — the
    fixture generator produces daily bars only.
    """
    start_s = start.strftime("%Y-%m-%d") if isinstance(start, datetime) else str(start)
    end_s = end.strftime("%Y-%m-%d") if isinstance(end, datetime) else str(end)
    return generate_fixture_prices(symbols=symbols, start=start_s, end=end_s)


@contextmanager
def offline_fallback() -> Iterator[None]:
    """Context manager: force ``ALPHAKIT_OFFLINE=1`` inside the block.

    Restores the previous value (or unsets the variable) on exit.
    Intended for tests and short-lived programmatic overrides.
    """
    prev = os.environ.get("ALPHAKIT_OFFLINE")
    os.environ["ALPHAKIT_OFFLINE"] = "1"
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("ALPHAKIT_OFFLINE", None)
        else:
            os.environ["ALPHAKIT_OFFLINE"] = prev

"""Tests for the live crypto strategy roster (mv.api.roster).

Verifies the roster is the full crypto-capable set and that **every** strategy in
it actually runs on the loop's single-symbol close-only window — the guard that
keeps a catalog strategy needing a multi-asset panel from being wired into the
live ensemble where it would error or silently flatline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from mv.api.roster import (
    available_names,
    default_crypto_roster,
    roster_from_names,
    roster_names,
)

_SYMBOL = "BTC/USDT"


def _close_window(n: int = 240) -> pd.DataFrame:
    """A single-symbol close-only window like the loop builds, long enough to warm
    up every strategy (the 50/200 SMA needs 200 bars)."""
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    rng = np.random.default_rng(7)
    prices = 40_000.0 * np.cumprod(1.0 + rng.normal(0.0, 0.01, size=n))
    return pd.DataFrame({_SYMBOL: prices}, index=idx)


def test_roster_is_the_full_crypto_set() -> None:
    names = roster_names(default_crypto_roster())
    assert len(names) == 9
    assert len(set(names)) == 9  # unique
    assert {"ema_cross_12_26", "zscore_reversion", "rsi_reversion_2"} <= set(names)


def test_every_strategy_runs_on_the_close_only_window() -> None:
    window = _close_window()
    for strategy in default_crypto_roster():
        weights = strategy.generate_signals(window)
        assert _SYMBOL in weights.columns, strategy.name
        latest = weights[_SYMBOL].iloc[-1]
        # A tradeable signal: NaN (treated as flat by the loop) or within [-1, 1].
        assert pd.isna(latest) or -1.0 <= float(latest) <= 1.0, strategy.name


def test_roster_from_names_selects_subset_and_skips_unknown() -> None:
    chosen = roster_from_names(["ema_cross_12_26", "bogus", " zscore_reversion "])
    assert roster_names(chosen) == ["ema_cross_12_26", "zscore_reversion"]


def test_available_names_matches_default_roster() -> None:
    assert available_names() == roster_names(default_crypto_roster())

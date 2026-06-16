"""Unit tests for magic_formula."""

from __future__ import annotations

import numpy as np
import pandas as pd
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.value.magic_formula.strategy import MagicFormula


def _panel(seed: int = 42, years: float = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2010-01-01", periods=n, freq="B")
    data = {}
    for i, sym in enumerate(["A", "B", "C", "D", "E"]):
        drift = 0.0003 * (i - 2)
        noise = 0.012 * rng.standard_normal(n)
        data[sym] = 100.0 * np.exp(np.cumsum(drift + noise))
    return pd.DataFrame(data, index=idx)


def test_satisfies_protocol() -> None:
    assert isinstance(MagicFormula(), StrategyProtocol)


def test_metadata() -> None:
    s = MagicFormula()
    assert s.name == "magic_formula"
    assert s.family == "value"


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["A"], dtype=float)
    assert MagicFormula().generate_signals(empty).empty


def test_single_asset_returns_zero() -> None:
    idx = pd.date_range("2010-01-01", periods=1000, freq="B")
    prices = pd.DataFrame({"A": 100.0 + np.arange(1000) * 0.01}, index=idx)
    weights = MagicFormula().generate_signals(prices)
    assert (weights == 0.0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _panel()
    weights = MagicFormula().generate_signals(prices)
    assert (weights.iloc[:756] == 0.0).all().all()


def test_generates_nonzero_weights() -> None:
    prices = _panel()
    weights = MagicFormula().generate_signals(prices)
    mature = weights.iloc[766:]
    assert (mature != 0).any().any(), "Expected non-zero weights"


def test_long_only_mode() -> None:
    prices = _panel()
    s = MagicFormula(long_only=True)
    weights = s.generate_signals(prices)
    assert (weights >= -1e-10).all().all()


def test_deterministic() -> None:
    prices = _panel()
    a = MagicFormula().generate_signals(prices)
    b = MagicFormula().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)

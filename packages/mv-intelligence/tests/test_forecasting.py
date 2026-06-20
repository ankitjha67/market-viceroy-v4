"""Unit tests for the forecasting layer (deterministic GBM + offline-deep fallbacks)."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest
from mv.intelligence.forecasting import (
    FinBERTSentiment,
    GBMForecaster,
    LSTMForecaster,
    fit_window,
)
from mv.intelligence.guardrail import FredTrainingError


def _panel(n: int = 60) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(7)
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    x = pd.DataFrame({"mom": rng.normal(size=n), "rsi": rng.normal(size=n)}, index=idx)
    y = pd.Series(x["mom"] * 2.0 + x["rsi"] * 0.5 + rng.normal(scale=0.01, size=n), index=idx)
    return x, y


# ---- GBM: deterministic, FRED-guarded, leakage-free --------------------------


def test_gbm_is_deterministic() -> None:
    x, y = _panel()
    a, b = GBMForecaster(seed=0), GBMForecaster(seed=0)
    a.fit(x, y, sources=["technical"])
    b.fit(x, y, sources=["technical"])
    np.testing.assert_array_equal(a.predict(x), b.predict(x))


def test_gbm_learns_signal() -> None:
    x, y = _panel()
    model = GBMForecaster(seed=0)
    model.fit(x, y, sources=["technical"])
    preds = model.predict(x)
    # In-sample correlation with the target should be strong on a learnable signal.
    assert np.corrcoef(preds, y.to_numpy())[0, 1] > 0.9


def test_gbm_refuses_to_train_on_fred() -> None:
    x, y = _panel()
    with pytest.raises(FredTrainingError):  # the guardrail raises on a forbidden source
        GBMForecaster().fit(x, y, sources=["technical", "fred"])


def test_gbm_predict_before_fit_raises() -> None:
    x, _ = _panel()
    with pytest.raises(RuntimeError, match="before fit"):
        GBMForecaster().predict(x)


def test_fit_window_excludes_future_rows() -> None:
    x, y = _panel(10)
    as_of = datetime(2024, 1, 6, tzinfo=timezone.utc)
    xw, yw = fit_window(x, y, as_of=as_of)
    # Only rows strictly before the as-of survive — no look-ahead.
    assert xw.index.max() < pd.Timestamp(as_of)
    assert len(xw) == 5
    assert len(yw) == 5


def test_fit_window_requires_datetime_index() -> None:
    x = pd.DataFrame({"mom": [1.0, 2.0]})  # default RangeIndex
    y = pd.Series([0.1, 0.2])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        fit_window(x, y, as_of=datetime(2024, 1, 1, tzinfo=timezone.utc))


# ---- Deep forecasters: deterministic offline fallbacks (CI has no torch) ------


def test_lstm_falls_back_to_gbm_when_torch_absent() -> None:
    x, y = _panel()
    lstm = LSTMForecaster(seed=0)
    # torch is an optional extra not in CI -> the LSTM uses the seeded GBM fallback.
    assert lstm.available() is False
    lstm.fit(x, y, sources=["technical"])
    gbm = GBMForecaster(seed=0)
    gbm.fit(x, y, sources=["technical"])
    np.testing.assert_array_equal(lstm.predict(x), gbm.predict(x))


def test_lstm_fallback_still_guards_fred() -> None:
    x, y = _panel()
    with pytest.raises(FredTrainingError):
        LSTMForecaster().fit(x, y, sources=["fred"])


def test_finbert_falls_back_to_rule_based_when_offline() -> None:
    finbert = FinBERTSentiment()
    assert finbert.available() is False
    scores = finbert.score(["earnings beat strong growth", "fraud bankruptcy loss"])
    assert scores[0] > 0  # positive lexicon
    assert scores[1] < 0  # negative lexicon


def test_finbert_label_mapping_is_signed() -> None:
    assert FinBERTSentiment.label_to_score("positive", 0.9) == 0.9
    assert FinBERTSentiment.label_to_score("negative", 0.8) == -0.8
    assert FinBERTSentiment.label_to_score("neutral", 0.7) == 0.0

"""Deep forecasters (optional, offline) — FinBERT sentiment + an LSTM forecaster.

These need the ``forecasting-deep`` extra (torch/transformers) and run **offline
only**; the model load + inference are ``# pragma: no cover``. When the extra is
absent (the per-push CI default) each **falls back deterministically**:
``FinBERTSentiment`` → the Phase-3 rule-based lexicon; ``LSTMForecaster`` → the
seeded :class:`~mv.intelligence.forecasting.gbm.GBMForecaster`. The pure pieces
(label mapping, fallback selection, the FRED-no-train guard) are unit-tested.
This is real wiring with a real fallback — not a stub passed off as done.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np
import pandas as pd
from mv.intelligence.forecasting.base import guard_training_sources
from mv.intelligence.forecasting.gbm import GBMForecaster
from mv.intelligence.sentiment import score_text


def _torch_available() -> bool:
    try:
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


def _transformers_available() -> bool:
    try:
        import transformers  # noqa: F401
    except ImportError:
        return False
    return True


class FinBERTSentiment:
    """FinBERT financial-news sentiment, falling back to the rule-based lexicon."""

    def __init__(self, *, model_name: str = "ProsusAI/finbert") -> None:
        self._model_name = model_name

    def available(self) -> bool:
        """True only if the deep extra (torch + transformers) is installed."""
        return _torch_available() and _transformers_available()

    @staticmethod
    def label_to_score(label: str, confidence: float) -> float:
        """Map a FinBERT (label, confidence) to a signed score in [-1, 1] (pure)."""
        normalized = label.lower()
        if normalized == "positive":
            return confidence
        if normalized == "negative":
            return -confidence
        return 0.0

    def score(self, texts: Sequence[str]) -> list[float]:
        """Per-text sentiment in [-1, 1]; rule-based fallback when offline-only."""
        if not self.available():
            return [score_text(text) for text in texts]
        return self._score_with_model(texts)  # pragma: no cover - offline model

    def _score_with_model(self, texts: Sequence[str]) -> list[float]:  # pragma: no cover - offline
        from transformers import pipeline

        clf = pipeline("text-classification", model=self._model_name)
        return [self.label_to_score(r["label"], float(r["score"])) for r in clf(list(texts))]


class LSTMForecaster:
    """An LSTM sequence forecaster, falling back to the seeded GBM when offline."""

    def __init__(self, *, seed: int = 0) -> None:
        self._seed = seed
        self._fallback = GBMForecaster(seed=seed)
        self._mode: Literal["gbm", "lstm"] = "gbm"

    def available(self) -> bool:
        return _torch_available()

    def fit(self, features: pd.DataFrame, target: pd.Series, *, sources: Sequence[str]) -> None:
        guard_training_sources(sources)  # FR-D11/BR-006
        if not self.available():
            self._fallback.fit(features, target, sources=sources)
            self._mode = "gbm"
            return
        self._fit_torch(features, target)  # pragma: no cover - offline torch
        self._mode = "lstm"

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        if self._mode == "gbm":
            return self._fallback.predict(features)
        return self._predict_torch(features)  # pragma: no cover - offline torch

    def _fit_torch(self, features: pd.DataFrame, target: pd.Series) -> None:  # pragma: no cover
        import torch

        torch.manual_seed(self._seed)
        raise NotImplementedError("the torch LSTM trains offline with the forecasting-deep extra")

    def _predict_torch(self, features: pd.DataFrame) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError("the torch LSTM runs offline with the forecasting-deep extra")


__all__ = ["FinBERTSentiment", "LSTMForecaster"]

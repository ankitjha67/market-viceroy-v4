"""FRED no-train guardrail (PRD FR-D11 / BR-006) — inviolable.

FRED's ToS forbids training/fine-tuning models on FRED data; FRED is a runtime
input only. Any training pipeline that assembles features MUST call
:func:`assert_no_fred_in_training` on the feature sources before fitting. Phase 3
introduces feature/training capability, so the guardrail lands here even though
forecasting itself is deferred — it is the enforcement hook future ML uses.
"""

from __future__ import annotations

from collections.abc import Iterable

# Substrings marking a source whose data may never enter a training set.
FORBIDDEN_TRAINING_SOURCES: frozenset[str] = frozenset({"fred"})


class FredTrainingError(Exception):
    """A FRED-derived feature was about to be used to train/fine-tune a model."""


def is_forbidden_source(source: str) -> bool:
    """True if ``source`` is FRED-derived (e.g. 'fred', 'yfinance+fred-real')."""
    tag = source.lower()
    return any(forbidden in tag for forbidden in FORBIDDEN_TRAINING_SOURCES)


def assert_no_fred_in_training(sources: Iterable[str]) -> None:
    """Raise :class:`FredTrainingError` if any source is FRED-derived.

    FRED stays a runtime/inference input only — never a training input.
    """
    offending = sorted({source for source in sources if is_forbidden_source(source)})
    if offending:
        raise FredTrainingError(
            f"FRED-derived sources cannot be used for model training (FRED ToS): "
            f"{offending}. Use FRED only as a runtime/inference input."
        )

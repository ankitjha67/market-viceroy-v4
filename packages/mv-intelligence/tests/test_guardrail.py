"""Unit tests for the FRED no-train guardrail (FR-D11/BR-006)."""

from __future__ import annotations

import pytest
from mv.intelligence.guardrail import (
    FredTrainingError,
    assert_no_fred_in_training,
    is_forbidden_source,
)


def test_non_fred_sources_pass() -> None:
    assert_no_fred_in_training(["sec_edgar", "technicals", "rss:reuters"])  # no raise


def test_fred_source_rejected() -> None:
    with pytest.raises(FredTrainingError, match="FRED ToS"):
        assert_no_fred_in_training(["sec_edgar", "fred"])


def test_fred_hybrid_source_rejected() -> None:
    # The macro hybrids (e.g. 'yfinance+fred-real') are FRED-derived.
    with pytest.raises(FredTrainingError):
        assert_no_fred_in_training(["yfinance+fred-real"])


def test_is_forbidden_source() -> None:
    assert is_forbidden_source("fred") is True
    assert is_forbidden_source("FRED:DGS10") is True
    assert is_forbidden_source("sec_edgar") is False

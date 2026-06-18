"""Unit tests for the feature-store frame validation (pure)."""

from __future__ import annotations

import pandas as pd
import pytest
from mv.intelligence.store import FEATURE_COLUMNS, validate_feature_frame


def test_valid_frame_passes() -> None:
    frame = pd.DataFrame({col: [] for col in FEATURE_COLUMNS})
    validate_feature_frame(frame)  # no raise


def test_missing_columns_raise() -> None:
    frame = pd.DataFrame({"instrument": [], "value": []})
    with pytest.raises(ValueError, match="missing columns"):
        validate_feature_frame(frame)

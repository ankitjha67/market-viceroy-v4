"""Unit tests for SEC EDGAR normalization (point-in-time by filing date)."""

from __future__ import annotations

import pandas as pd
from mv.intelligence.sources.sec_edgar import normalize_company_facts

# A minimal companyfacts-shaped fixture: the 2022 revenue is only *filed* in
# early 2023 (point-in-time), and a 2023 revenue filed in 2024.
_RAW = {
    "facts": {
        "us-gaap": {
            "Revenues": {
                "units": {
                    "USD": [
                        {"end": "2022-12-31", "val": 1000, "filed": "2023-02-15", "form": "10-K"},
                        {"end": "2023-12-31", "val": 1200, "filed": "2024-02-15", "form": "10-K"},
                    ]
                }
            },
            "NetIncomeLoss": {
                "units": {"USD": [{"end": "2022-12-31", "val": 100, "filed": "2023-02-15"}]}
            },
        }
    }
}


def test_normalizes_concepts_to_features() -> None:
    out = normalize_company_facts(_RAW, instrument="AAPL")
    assert set(out["feature_name"]) == {"revenue", "net_income"}
    assert set(out["source"]) == {"sec_edgar"}
    assert list(out.columns) == ["instrument", "feature_name", "ts", "value", "source"]


def test_uses_filing_date_not_period_end() -> None:
    out = normalize_company_facts(_RAW, instrument="AAPL")
    revenue = out[out["feature_name"] == "revenue"].sort_values("ts")
    # The 2022 revenue (1000) is stamped by its FILING date 2023-02-15, not 2022-12-31.
    assert revenue.iloc[0]["ts"] == pd.Timestamp("2023-02-15", tz="UTC")
    assert revenue.iloc[0]["value"] == 1000.0
    assert revenue.iloc[1]["ts"] == pd.Timestamp("2024-02-15", tz="UTC")


def test_skips_missing_concepts_and_values() -> None:
    raw = {
        "facts": {"us-gaap": {"Assets": {"units": {"USD": [{"val": None, "filed": "2023-01-01"}]}}}}
    }
    out = normalize_company_facts(raw, instrument="MSFT")
    assert out.empty


def test_empty_payload_yields_empty_frame() -> None:
    out = normalize_company_facts({}, instrument="AAPL")
    assert out.empty
    assert list(out.columns) == ["instrument", "feature_name", "ts", "value", "source"]

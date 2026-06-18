"""SEC EDGAR fundamentals (PRD FR-I1) — point-in-time by FILING date.

The critical point-in-time rule: a fundamental value is stamped by the date it
was **filed** (when it became knowable), NOT the fiscal period end. Using the
period end would leak — the 2022 annual revenue is only public when the 10-K is
filed in early 2023. The normalization is pure (unit-tested on a fixture); the
keyless EDGAR fetch (10 req/s, descriptive User-Agent required) is gated.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from mv.intelligence.store import FEATURE_COLUMNS

SOURCE = "sec_edgar"

# EDGAR us-gaap concept -> feature name.
CONCEPTS: dict[str, str] = {
    "Revenues": "revenue",
    "NetIncomeLoss": "net_income",
    "Assets": "assets",
    "Liabilities": "liabilities",
    "StockholdersEquity": "equity",
    "EarningsPerShareDiluted": "eps_diluted",
}


def normalize_company_facts(
    raw: dict[str, Any],
    *,
    instrument: str,
    concepts: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Convert an EDGAR companyfacts payload into point-in-time feature rows.

    Each fact becomes a row stamped by its ``filed`` date (the as-of time).
    Returns a frame with :data:`~mv.intelligence.store.FEATURE_COLUMNS`.
    """
    mapping = concepts if concepts is not None else CONCEPTS
    gaap = raw.get("facts", {}).get("us-gaap", {})
    rows: list[dict[str, Any]] = []
    for concept, feature_name in mapping.items():
        node = gaap.get(concept)
        if not node:
            continue
        for facts in node.get("units", {}).values():
            for fact in facts:
                filed = fact.get("filed")
                value = fact.get("val")
                if filed is None or value is None:
                    continue
                rows.append(
                    {
                        "instrument": instrument,
                        "feature_name": feature_name,
                        "ts": pd.Timestamp(filed, tz="UTC"),  # FILING date, not period end
                        "value": float(value),
                        "source": SOURCE,
                    }
                )
    return pd.DataFrame(rows, columns=list(FEATURE_COLUMNS))


def fetch_company_facts(
    cik: str, *, user_agent: str
) -> dict[str, Any]:  # pragma: no cover - network
    """Fetch a company's EDGAR facts (keyless; descriptive User-Agent required)."""
    import requests

    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    response = requests.get(url, headers={"User-Agent": user_agent}, timeout=30)
    response.raise_for_status()
    return dict(response.json())

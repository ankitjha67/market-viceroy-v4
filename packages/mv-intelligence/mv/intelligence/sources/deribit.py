"""Deribit public options data (keyless) -> chain summaries for the GEX engine.

Adopted from the Vibe-Trading review and the Appendix-B options-vendor open
decision: Deribit's public book summaries carry everything a v1 crypto GEX
engine needs — per-instrument open interest, mark IV, and the underlying price
— with no key and no cost. The fetch is offline-gated; instrument-name parsing
and payload normalization are pure and unit-tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

_API_URL = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency"

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}  # fmt: skip


@dataclass(frozen=True, slots=True)
class OptionSummary:
    """One option instrument's screen row (OI in contracts, IV as a fraction)."""

    strike: float
    expiry: datetime
    right: Literal["C", "P"]
    open_interest: float
    mark_iv: float  # 0.65 = 65 percent
    underlying: float


def parse_instrument_name(name: str) -> tuple[datetime, float, Literal["C", "P"]] | None:
    """Parse ``BTC-27JUN25-60000-C`` into (expiry, strike, right); None if not."""
    parts = name.split("-")
    if len(parts) != 4 or parts[3] not in ("C", "P"):
        return None
    raw = parts[1]
    try:
        day = int(raw[:-5])
        month = _MONTHS[raw[-5:-2].upper()]
        year = 2000 + int(raw[-2:])
        expiry = datetime(year, month, day, 8, 0, tzinfo=timezone.utc)  # Deribit 08:00 UTC
        strike = float(parts[2].replace("d", "."))
    except (KeyError, ValueError):
        return None
    right: Literal["C", "P"] = "C" if parts[3] == "C" else "P"
    return expiry, strike, right


def parse_book_summary(payload: dict[str, Any]) -> list[OptionSummary]:
    """Normalize a ``get_book_summary_by_currency`` payload into chain rows.

    Rows without OI, IV, or a parseable name are dropped — a gap in the chain
    is honest; a fabricated zero would distort the gamma profile.
    """
    out: list[OptionSummary] = []
    for row in payload.get("result", []) or []:
        parsed = parse_instrument_name(str(row.get("instrument_name") or ""))
        oi = row.get("open_interest")
        iv = row.get("mark_iv")
        under = row.get("underlying_price") or row.get("estimated_delivery_price")
        if parsed is None or not all(isinstance(v, (int, float)) for v in (oi, iv, under)):
            continue
        expiry, strike, right = parsed
        out.append(
            OptionSummary(
                strike=strike,
                expiry=expiry,
                right=right,
                open_interest=float(oi),
                mark_iv=float(iv) / 100.0,  # Deribit reports percent
                underlying=float(under),
            )
        )
    return out


def fetch_option_chain(
    currency: str = "BTC",
) -> list[OptionSummary]:  # pragma: no cover - network
    """Fetch the full option book summary for ``currency`` (keyless)."""
    import requests

    response = requests.get(_API_URL, params={"currency": currency, "kind": "option"}, timeout=30)
    response.raise_for_status()
    return parse_book_summary(response.json())


__all__ = ["OptionSummary", "fetch_option_chain", "parse_book_summary", "parse_instrument_name"]

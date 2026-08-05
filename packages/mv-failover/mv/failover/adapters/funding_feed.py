"""Perp funding-rate + open-interest feed (Binance USD-M public, via CCXT).

Adopted from the Vibe-Trading review: funding is a first-class market input, not
an afterthought. This adapter fetches current perp funding rates and open
interest for the watchlist (public endpoints, keyless) so the loop can expose a
real ``flow`` feature to the agents, the deck can show crowd positioning, and
the funding-carry/basis strategies get real data instead of proxies. The
network calls are offline-gated; the spot-to-perp mapping and normalization are
pure and unit-tested. Rates are per funding interval (typically 8h) as decimal
fractions, exactly as the venue reports them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FundingRate:
    """One perp's current funding state (rate is per interval, e.g. per 8h)."""

    symbol: str  # spot-style symbol, e.g. "BTC/USDT"
    rate: float  # funding rate as a decimal fraction (0.0001 = 1 bp)
    open_interest: float | None = None  # contracts/base units when available


def perp_symbol(spot_symbol: str) -> str:
    """Map a spot pair to its CCXT linear-perp symbol (``BTC/USDT:USDT``)."""
    return f"{spot_symbol}:USDT" if ":" not in spot_symbol else spot_symbol


def spot_symbol(perp: str) -> str:
    """Inverse of :func:`perp_symbol` (``BTC/USDT:USDT`` -> ``BTC/USDT``)."""
    return perp.split(":", 1)[0]


def normalize_funding(raw: dict[str, dict[str, Any]]) -> dict[str, FundingRate]:
    """Normalize a CCXT ``fetch_funding_rates`` payload to spot-keyed rates.

    Entries with a missing/non-numeric ``fundingRate`` are dropped (an absent
    reading must never masquerade as 0 — the agents treat missing as no
    coverage, per the point-in-time discipline).
    """
    out: dict[str, FundingRate] = {}
    for key, entry in raw.items():
        rate = entry.get("fundingRate")
        if not isinstance(rate, (int, float)) or isinstance(rate, bool):
            continue
        sym = spot_symbol(str(entry.get("symbol") or key))
        oi = entry.get("openInterestAmount")
        out[sym] = FundingRate(
            symbol=sym,
            rate=float(rate),
            open_interest=float(oi) if isinstance(oi, (int, float)) else None,
        )
    return out


def funding_flow_score(rate: float, *, saturation: float = 0.0005) -> float:
    """Map a funding rate to a directional crowd-``flow`` feature in [-1, 1].

    Positive funding means longs pay shorts: the crowd is net long. The score
    saturates at ``saturation`` (5 bps per interval is already an extreme
    reading on majors), so outliers cannot dominate the analyst blend.
    """
    if saturation <= 0:
        return 0.0
    return max(-1.0, min(1.0, rate / saturation))


def fetch_funding_rates(
    symbols: list[str],
) -> dict[str, FundingRate]:  # pragma: no cover - network
    """Fetch current funding rates + OI for ``symbols`` from Binance USD-M."""
    import ccxt

    exchange = ccxt.binanceusdm({"enableRateLimit": True})
    perps = [perp_symbol(s) for s in symbols]
    raw: dict[str, dict[str, Any]] = exchange.fetch_funding_rates(perps)
    normalized = normalize_funding(raw)
    for sym in list(normalized):
        if normalized[sym].open_interest is None:
            try:
                oi = exchange.fetch_open_interest(perp_symbol(sym))
                amount = oi.get("openInterestAmount")
                if isinstance(amount, (int, float)):
                    normalized[sym] = FundingRate(
                        symbol=sym, rate=normalized[sym].rate, open_interest=float(amount)
                    )
            except Exception:  # OI is enrichment; funding alone is still useful
                continue
    return normalized


__all__ = [
    "FundingRate",
    "fetch_funding_rates",
    "funding_flow_score",
    "normalize_funding",
    "perp_symbol",
    "spot_symbol",
]

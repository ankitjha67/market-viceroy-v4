"""USD->INR conversion for the paper loop — all values in INR (India-first).

Fetches the live USD/INR reference rate through the failover governor's FX domain
(Frankfurter), with a fixed fallback when offline, and scales a normalized OHLCV
frame into INR. Scaling every price by one constant is signal-neutral (the
cross/momentum strategies are scale-invariant), so the whole paper pipeline —
journal, fills, decisions, positions, equity — ends up denominated in INR. The
rate is ``Decimal``; the price multiply runs in the float data plane.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import polars as pl
from mv.failover.registry import FX_RATES

# Conservative default if the FX governor is unreachable (≈ recent USD/INR).
_FALLBACK = Decimal("83")


def latest_rate(frame: pl.DataFrame, *, fallback: Decimal = _FALLBACK) -> Decimal:
    """The most recent close of an FX bar frame as a ``Decimal`` (fallback if empty)."""
    if frame.height == 0 or "close" not in frame.columns:
        return fallback
    value = frame.get_column("close").tail(1).item()
    if value is None:
        return fallback
    rate = Decimal(str(value))
    return rate if rate > 0 else fallback


def usd_inr_rate(
    router: Any, *, fallback: Decimal = _FALLBACK
) -> Decimal:  # pragma: no cover - network
    """Live USD->INR via the FX governor; the fixed ``fallback`` on any failure."""
    try:
        result = router.get_bars(FX_RATES, "USD/INR", "1d", limit=1)
        return latest_rate(result.frame, fallback=fallback)
    except Exception:  # any FX failure -> deterministic fallback rate
        return fallback


def scale_prices(frame: pl.DataFrame, rate: Decimal) -> pl.DataFrame:
    """Return a copy of an OHLCV frame with O/H/L/C multiplied by ``rate``.

    Volume is left untouched. Linear price scaling is signal-neutral, so running
    the loop over the scaled frame denominates the entire pipeline in INR.
    """
    factor = float(rate)
    price_cols = [c for c in ("open", "high", "low", "close") if c in frame.columns]
    return frame.with_columns([(pl.col(c) * factor).alias(c) for c in price_cols])


__all__ = ["latest_rate", "scale_prices", "usd_inr_rate"]

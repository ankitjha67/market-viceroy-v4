"""Generic NautilusTrader instrument construction for the crypto watchlist.

The single-symbol loop used ``TestInstrumentProvider``'s BTC/USDT preset; the
multi-instrument loop needs an instrument for any ``BASE/USDT`` pair. We build a
Binance ``CurrencyPair`` from NautilusTrader's built-in currency registry with
uniform paper precision — fine because the loop trades on **INR-scaled** prices
(every price is well above ₹1 after the USD→INR scale, so 2-dp price precision is
ample) and 8-dp size precision keeps a small book tradeable. Live trading would
pull exact instrument specs from the exchange; this is the paper venue only.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.objects import Currency, Price, Quantity

_FEE = Decimal("0.001")  # 0.1% maker/taker — Binance spot default


def crypto_instrument(symbol: str, *, venue: str = "BINANCE") -> Any:
    """Build a Binance ``CurrencyPair`` instrument for ``symbol`` (e.g. ``"SOL/USDT"``).

    Raises:
        ValueError: If ``symbol`` is not ``BASE/QUOTE`` or names a currency the
            registry does not know.
    """
    if symbol.count("/") != 1:
        raise ValueError(f"symbol must be BASE/QUOTE, got {symbol!r}")
    base_code, quote_code = symbol.split("/", 1)
    try:
        base = Currency.from_str(base_code)
        quote = Currency.from_str(quote_code)
    except Exception as exc:  # unknown currency in the registry
        raise ValueError(f"unknown currency in {symbol!r}: {exc}") from exc
    raw = Symbol(base_code + quote_code)
    return CurrencyPair(
        instrument_id=InstrumentId(raw, Venue(venue)),
        raw_symbol=raw,
        base_currency=base,
        quote_currency=quote,
        price_precision=2,
        size_precision=8,
        price_increment=Price.from_str("0.01"),
        size_increment=Quantity.from_str("0.00000001"),
        margin_init=Decimal("0"),
        margin_maint=Decimal("0"),
        maker_fee=_FEE,
        taker_fee=_FEE,
        ts_event=0,
        ts_init=0,
    )


__all__ = ["crypto_instrument"]

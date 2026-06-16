"""Validator and happy-path tests for every pydantic model in core."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from alphakit.core.data.bar import Bar
from alphakit.core.data.option_chain import OptionChain, OptionQuote, OptionRight
from alphakit.core.data.order_book import BookLevel, OrderBook
from alphakit.core.data.tick import Tick, TickSide
from alphakit.core.instruments.base import AssetClass, Instrument
from alphakit.core.instruments.crypto import CryptoKind, CryptoPair
from alphakit.core.instruments.equity import Equity
from alphakit.core.instruments.future import Future
from alphakit.core.instruments.fx import FXPair, FXTenor
from alphakit.core.instruments.option import Option, OptionStyle
from alphakit.core.signals.signal import Signal, SignalDirection
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Bar
# ---------------------------------------------------------------------------
def test_bar_happy_path() -> None:
    bar = Bar(
        timestamp=datetime(2026, 4, 15),
        symbol="SPY",
        open=500.0,
        high=510.0,
        low=498.0,
        close=505.0,
        volume=1_000_000.0,
    )
    assert bar.symbol == "SPY"
    assert bar.close == 505.0


@pytest.mark.parametrize(
    ("patch", "match"),
    [
        ({"high": 490.0}, "high.*low"),
        ({"high": 499.0}, "high.*>=.*open"),
        ({"low": 506.0}, "low.*<=.*open"),
        # inf passes pydantic's ge=0.0 and hits our model_validator.
        ({"open": float("inf")}, "finite"),
        # NaN fails pydantic's ge=0.0 first (NaN >= 0 is False in Python).
        ({"close": float("nan")}, r"greater_than_equal|finite"),
    ],
)
def test_bar_rejects_bad_input(patch: dict[str, float], match: str) -> None:
    base: dict[str, object] = {
        "timestamp": datetime(2026, 4, 15),
        "symbol": "SPY",
        "open": 500.0,
        "high": 510.0,
        "low": 498.0,
        "close": 505.0,
        "volume": 1_000_000.0,
    }
    base.update(patch)
    with pytest.raises((ValidationError, ValueError), match=match):
        Bar(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tick
# ---------------------------------------------------------------------------
def test_tick_happy_path() -> None:
    tick = Tick(
        timestamp=datetime(2026, 4, 15, 9, 30),
        symbol="SPY",
        price=505.0,
        size=100.0,
        side=TickSide.TRADE,
    )
    assert tick.side == TickSide.TRADE


def test_tick_rejects_non_positive_price() -> None:
    with pytest.raises(ValidationError):
        Tick(
            timestamp=datetime(2026, 4, 15),
            symbol="SPY",
            price=0.0,
            size=100.0,
            side=TickSide.BID,
        )


def test_tick_rejects_infinite_size() -> None:
    with pytest.raises((ValidationError, ValueError), match="finite"):
        Tick(
            timestamp=datetime(2026, 4, 15),
            symbol="SPY",
            price=505.0,
            size=float("inf"),
            side=TickSide.ASK,
        )


# ---------------------------------------------------------------------------
# OrderBook / BookLevel
# ---------------------------------------------------------------------------
def test_order_book_happy_path() -> None:
    book = OrderBook(
        timestamp=datetime(2026, 4, 15),
        symbol="SPY",
        bids=(BookLevel(price=499.0, size=100), BookLevel(price=498.0, size=200)),
        asks=(BookLevel(price=501.0, size=100), BookLevel(price=502.0, size=200)),
    )
    assert book.best_bid == 499.0
    assert book.best_ask == 501.0
    assert book.mid == 500.0
    assert book.spread == 2.0


def test_order_book_empty_side_returns_none() -> None:
    book = OrderBook(
        timestamp=datetime(2026, 4, 15),
        symbol="SPY",
        bids=(),
        asks=(),
    )
    assert book.best_bid is None
    assert book.best_ask is None
    assert book.mid is None
    assert book.spread is None


def test_order_book_rejects_crossed_book() -> None:
    with pytest.raises(ValidationError, match="crossed"):
        OrderBook(
            timestamp=datetime(2026, 4, 15),
            symbol="SPY",
            bids=(BookLevel(price=502.0, size=100),),
            asks=(BookLevel(price=501.0, size=100),),
        )


def test_order_book_rejects_unsorted_bids() -> None:
    with pytest.raises(ValidationError, match=r"bids.*sorted"):
        OrderBook(
            timestamp=datetime(2026, 4, 15),
            symbol="SPY",
            bids=(BookLevel(price=498.0, size=100), BookLevel(price=499.0, size=100)),
            asks=(BookLevel(price=501.0, size=100),),
        )


def test_order_book_rejects_unsorted_asks() -> None:
    with pytest.raises(ValidationError, match=r"asks.*sorted"):
        OrderBook(
            timestamp=datetime(2026, 4, 15),
            symbol="SPY",
            bids=(BookLevel(price=499.0, size=100),),
            asks=(BookLevel(price=502.0, size=100), BookLevel(price=501.0, size=100)),
        )


# ---------------------------------------------------------------------------
# OptionChain / OptionQuote
# ---------------------------------------------------------------------------
def test_option_chain_accessors() -> None:
    quotes = (
        OptionQuote(
            expiry=date(2026, 6, 19), strike=500.0, right=OptionRight.CALL, bid=5.0, ask=5.1
        ),
        OptionQuote(
            expiry=date(2026, 6, 19), strike=510.0, right=OptionRight.PUT, bid=10.0, ask=10.2
        ),
        OptionQuote(expiry=date(2026, 9, 18), strike=500.0, right=OptionRight.CALL),
    )
    chain = OptionChain(
        as_of=datetime(2026, 4, 15),
        underlying="SPY",
        spot=505.0,
        quotes=quotes,
    )
    assert chain.expiries() == (date(2026, 6, 19), date(2026, 9, 18))
    assert chain.strikes() == (500.0, 510.0)
    assert chain.strikes(expiry=date(2026, 6, 19)) == (500.0, 510.0)
    assert chain.filter(expiry=date(2026, 6, 19), right=OptionRight.CALL) == (quotes[0],)
    assert chain.filter(right=OptionRight.PUT) == (quotes[1],)
    assert quotes[0].mid == pytest.approx(5.05)
    assert quotes[2].mid is None


# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------
def test_equity_defaults_and_str() -> None:
    eq = Equity(symbol="SPY", exchange="NYSE", currency="USD")
    assert eq.asset_class == AssetClass.EQUITY
    assert str(eq) == "equity:NYSE:SPY"
    assert eq.is_etf is False


def test_option_defaults() -> None:
    opt = Option(
        symbol="SPY 260619C00500000",
        exchange="CBOE",
        currency="USD",
        underlying="SPY",
        strike=500.0,
        expiry=date(2026, 6, 19),
        right=OptionRight.CALL,
    )
    assert opt.style == OptionStyle.AMERICAN
    assert opt.multiplier == 100.0


def test_future_dated_and_continuous() -> None:
    dated = Future(
        symbol="ESM26",
        exchange="CME",
        currency="USD",
        root="ES",
        expiry=date(2026, 6, 19),
        tick_size=0.25,
        multiplier=50.0,
    )
    assert dated.expiry == date(2026, 6, 19)

    continuous = Future(
        symbol="ES.c.0",
        exchange="CME",
        currency="USD",
        root="ES",
        expiry=None,
        tick_size=0.25,
        multiplier=50.0,
        splicing_method="panama",
    )
    assert continuous.splicing_method == "panama"


def test_future_rejects_continuous_without_splicing() -> None:
    with pytest.raises(ValidationError, match="splicing_method"):
        Future(
            symbol="ES.c.0",
            exchange="CME",
            currency="USD",
            root="ES",
            expiry=None,
            tick_size=0.25,
            multiplier=50.0,
        )


def test_fx_pair_valid() -> None:
    pair = FXPair(
        symbol="EURUSD",
        exchange="OANDA",
        currency="USD",
        base="EUR",
        quote="USD",
    )
    assert pair.tenor == FXTenor.SPOT


def test_fx_pair_rejects_base_equals_quote() -> None:
    with pytest.raises(ValidationError, match="base"):
        FXPair(
            symbol="USDUSD",
            exchange="OANDA",
            currency="USD",
            base="USD",
            quote="USD",
        )


def test_crypto_pair_spot_and_dated() -> None:
    spot = CryptoPair(
        symbol="BTC/USDT",
        exchange="BINANCE",
        currency="USDT",
        base="BTC",
        quote="USDT",
    )
    assert spot.kind == CryptoKind.SPOT

    dated = CryptoPair(
        symbol="BTC-USDT-260926",
        exchange="BINANCE",
        currency="USDT",
        base="BTC",
        quote="USDT",
        kind=CryptoKind.DATED,
        expiry=date(2026, 9, 26),
    )
    assert dated.expiry == date(2026, 9, 26)


def test_crypto_pair_rejects_dated_without_expiry() -> None:
    with pytest.raises(ValidationError, match="dated"):
        CryptoPair(
            symbol="BTC-USDT-?",
            exchange="BINANCE",
            currency="USDT",
            base="BTC",
            quote="USDT",
            kind=CryptoKind.DATED,
        )


def test_crypto_pair_rejects_perp_with_expiry() -> None:
    with pytest.raises(ValidationError, match="perp"):
        CryptoPair(
            symbol="BTC-PERP",
            exchange="BINANCE",
            currency="USDT",
            base="BTC",
            quote="USDT",
            kind=CryptoKind.PERP,
            expiry=date(2026, 9, 26),
        )


def test_crypto_pair_rejects_same_base_quote() -> None:
    with pytest.raises(ValidationError, match="differ"):
        CryptoPair(
            symbol="BTC/BTC",
            exchange="BINANCE",
            currency="BTC",
            base="BTC",
            quote="BTC",
        )


def test_instrument_base_has_str_repr() -> None:
    inst = Instrument(
        symbol="CUSTOM",
        exchange="VENUE",
        currency="USD",
        asset_class=AssetClass.BOND,
    )
    assert "bond" in str(inst)


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------
def test_signal_happy_path() -> None:
    eq = Equity(symbol="SPY", exchange="NYSE", currency="USD")
    sig = Signal(
        timestamp=datetime(2026, 4, 15),
        instrument=eq,
        direction=SignalDirection.LONG,
        size=0.5,
        confidence=0.8,
    )
    assert sig.direction == SignalDirection.LONG
    assert sig.confidence == 0.8


def test_signal_flat_must_have_zero_size() -> None:
    eq = Equity(symbol="SPY", exchange="NYSE", currency="USD")
    with pytest.raises(ValidationError, match="FLAT"):
        Signal(
            timestamp=datetime(2026, 4, 15),
            instrument=eq,
            direction=SignalDirection.FLAT,
            size=0.5,
        )


def test_signal_rejects_nan_confidence() -> None:
    eq = Equity(symbol="SPY", exchange="NYSE", currency="USD")
    with pytest.raises(ValidationError):
        Signal(
            timestamp=datetime(2026, 4, 15),
            instrument=eq,
            direction=SignalDirection.LONG,
            size=0.5,
            confidence=1.5,
        )

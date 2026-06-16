"""Tests for DataFeedProtocol.fetch_chain default behaviour.

ADR-003 adds ``fetch_chain`` to ``DataFeedProtocol``. Non-options
adapters delegate their implementation to
:func:`raise_chain_not_supported`, so the error message format stays
uniform across every feed that declines to serve chains. These tests
pin that contract down.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest
from alphakit.core.data import OptionChain, OptionQuote, OptionRight
from alphakit.core.protocols import DataFeedProtocol, raise_chain_not_supported


class _PriceOnlyFeed:
    """Feed that declines option chains via the shared helper."""

    name: str = "price-only"

    def fetch(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        return pd.DataFrame({s: [1.0] for s in symbols})

    def fetch_chain(self, underlying: str, as_of: datetime) -> OptionChain:
        raise_chain_not_supported(self.name)


class _OptionsFeed:
    """Feed that implements both methods."""

    name: str = "options-feed"

    def fetch(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        return pd.DataFrame({s: [1.0] for s in symbols})

    def fetch_chain(self, underlying: str, as_of: datetime) -> OptionChain:
        return OptionChain(
            as_of=as_of,
            underlying=underlying,
            spot=100.0,
            quotes=(
                OptionQuote(
                    expiry=date(2024, 12, 20),
                    strike=100.0,
                    right=OptionRight.CALL,
                ),
            ),
        )


def test_raise_chain_not_supported_uses_feed_name() -> None:
    with pytest.raises(NotImplementedError, match="'my-feed'"):
        raise_chain_not_supported("my-feed")


def test_price_only_feed_refuses_chain_with_its_name() -> None:
    feed = _PriceOnlyFeed()
    with pytest.raises(NotImplementedError, match="price-only"):
        feed.fetch_chain("SPY", datetime(2024, 6, 1))


def test_options_feed_returns_option_chain() -> None:
    feed = _OptionsFeed()
    chain = feed.fetch_chain("SPY", datetime(2024, 6, 1))
    assert isinstance(chain, OptionChain)
    assert chain.underlying == "SPY"


def test_fetch_still_works_alongside_fetch_chain_refusal() -> None:
    feed = _PriceOnlyFeed()
    df = feed.fetch(["AAA"], datetime(2024, 1, 1), datetime(2024, 1, 2))
    assert list(df.columns) == ["AAA"]


def test_protocol_runtime_check_accepts_price_only_feed() -> None:
    feed = _PriceOnlyFeed()
    assert isinstance(feed, DataFeedProtocol)


def test_protocol_runtime_check_accepts_options_feed() -> None:
    feed = _OptionsFeed()
    assert isinstance(feed, DataFeedProtocol)


def test_yfinance_adapter_fetch_chain_raises() -> None:
    """YFinance (price-only) must refuse chain requests loudly."""
    from alphakit.data.equities.yfinance_adapter import YFinanceAdapter

    adapter = YFinanceAdapter()
    with pytest.raises(NotImplementedError, match="yfinance"):
        adapter.fetch_chain("SPY", datetime(2024, 1, 1))

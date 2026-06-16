"""Synthetic option-chain feed (ADR-005).

Generates :class:`OptionChain` snapshots from an underlying price
series via Black-Scholes pricing with realized-volatility-based
implied vol. Used as the default Phase 2 options feed in lieu of a
live Polygon integration (ADR-004).

Methodology
-----------
1. Fetch ~550 calendar days (≈252 trading bars) of underlying closes
   ending at ``as_of`` from the underlying feed.
2. Compute trailing 30-/60-/90-day realized volatility from log
   returns; the appropriate window is selected per expiry.
3. Build a 9-point strike grid at ``{0.80, 0.85, …, 1.20} × spot`` and
   a 11-14-point expiry grid from the union of 4 weekly, 6 monthly,
   and 4 quarterly third-Friday dates (date-level dedup).
4. For every (strike, expiry, right) combination, price via
   Black-Scholes and record the quote with BS-computed greeks.

Known limitations (documented in ``docs/feeds/synthetic-options.md``
and ``docs/deviations.md``):

* Flat vol across strikes — no IV skew.
* No bid-ask spread modelling (``bid == ask == last == mid``).
* No realistic volume / open interest.
* Greeks are BS-computed, not market-implied.

The feed is chain-only: :meth:`fetch` raises ``NotImplementedError``.
Register-at-import-time pattern mirrors every other Phase 2 adapter.
"""

from __future__ import annotations

import contextlib
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from alphakit.core.data import OptionChain, OptionQuote, OptionRight
from alphakit.core.protocols import DataFeedProtocol
from alphakit.data.options import bs
from alphakit.data.registry import FeedRegistry

STRIKE_MULTIPLIERS: tuple[float, ...] = (
    0.80,
    0.85,
    0.90,
    0.95,
    1.00,
    1.05,
    1.10,
    1.15,
    1.20,
)
"""Moneyness points used by the 9-strike grid. Symmetric around ATM."""

MIN_HISTORY_BARS: int = 252
"""Minimum underlying bars required to compute 90-day realized vol."""

DEFAULT_RISK_FREE_RATE: float = 0.045
"""Phase 2 placeholder risk-free rate. Replaced with a FRED-sourced
3-month T-bill yield in Phase 3."""

_HISTORY_CALENDAR_DAYS: int = 550
"""Calendar-day lookback on the underlying feed, tuned to return at
least ``MIN_HISTORY_BARS`` trading bars in all but the most
holiday-heavy windows."""


def _to_date(d: date | datetime) -> date:
    """Normalise a ``date | datetime`` to a ``date``."""
    if isinstance(d, datetime):
        return d.date()
    return d


def _third_friday(year: int, month: int) -> date:
    """Third Friday of the given month — the standard monthly expiry."""
    first = date(year, month, 1)
    offset = (4 - first.weekday()) % 7  # Mon=0 … Fri=4
    first_friday = first + timedelta(days=offset)
    return first_friday + timedelta(days=14)


def _weekly_fridays(after: date, count: int) -> list[date]:
    """``count`` Fridays strictly after ``after``."""
    days_until_friday = (4 - after.weekday()) % 7
    if days_until_friday == 0:
        days_until_friday = 7
    first = after + timedelta(days=days_until_friday)
    return [first + timedelta(days=7 * i) for i in range(count)]


def _monthly_expiries(after: date, count: int) -> list[date]:
    """Next ``count`` third-Fridays strictly after ``after``."""
    result: list[date] = []
    year, month = after.year, after.month
    while len(result) < count:
        tf = _third_friday(year, month)
        if tf > after:
            result.append(tf)
        month += 1
        if month > 12:
            month = 1
            year += 1
    return result


def _quarterly_expiries(after: date, count: int) -> list[date]:
    """Next ``count`` third-Fridays in Mar/Jun/Sep/Dec after ``after``."""
    result: list[date] = []
    quarterly_months = (3, 6, 9, 12)
    idx = 0
    while len(result) < count:
        month = quarterly_months[idx % 4]
        year = after.year + idx // 4
        tf = _third_friday(year, month)
        if tf > after:
            result.append(tf)
        idx += 1
    return result


def build_expiry_grid(as_of: date) -> tuple[date, ...]:
    """Union of weekly+monthly+quarterly expiries after ``as_of``.

    A set collapses date-level duplicates (a monthly third Friday that
    also happens to be one of the next four weekly Fridays collapses
    to one entry). The raw pool has 4+6+4=14 candidates; post-dedup
    the grid typically holds 11-13 distinct dates depending on
    ``as_of``.
    """
    pool: set[date] = set()
    pool.update(_weekly_fridays(as_of, 4))
    pool.update(_monthly_expiries(as_of, 6))
    pool.update(_quarterly_expiries(as_of, 4))
    return tuple(sorted(pool))


def _select_sigma(dte_days: int, rv30: float, rv60: float, rv90: float) -> float:
    """Map days-to-expiry to the most-appropriate realized-vol window."""
    if dte_days < 45:
        return rv30
    if dte_days < 120:
        return rv60
    return rv90


def _realized_vol(log_returns: np.ndarray, window: int) -> float:
    """Annualised realized volatility over the trailing ``window`` returns."""
    tail = log_returns[-window:]
    return float(np.std(tail, ddof=1) * np.sqrt(252.0))


class SyntheticOptionsFeed:
    """Black-Scholes synthetic option-chain feed (``name='synthetic-options'``).

    Constructed without arguments in production; the default
    :attr:`underlying_feed` lazily resolves to the yfinance adapter via
    :class:`FeedRegistry`. Tests and alternative deployments pass an
    explicit ``underlying_feed`` in the constructor.
    """

    name: str = "synthetic-options"

    def __init__(self, underlying_feed: DataFeedProtocol | None = None) -> None:
        self._explicit_underlying = underlying_feed

    @property
    def underlying_feed(self) -> DataFeedProtocol:
        """Resolve the underlying-prices feed lazily.

        Lazy lookup avoids a hard import ordering between the synthetic
        adapter and the yfinance adapter, and lets callers override at
        construction time without rewiring the registry.
        """
        if self._explicit_underlying is not None:
            return self._explicit_underlying
        return FeedRegistry.get("yfinance")

    def fetch(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        """Synthetic feed is chain-only; fetch prices from the underlying feed."""
        raise NotImplementedError(
            f"{self.name!r} is chain-only; call underlying_feed.fetch for prices"
        )

    def fetch_chain(self, underlying: str, as_of: datetime) -> OptionChain:
        """Return a Black-Scholes option chain for ``underlying`` at ``as_of``.

        Raises
        ------
        ValueError
            If the underlying feed returns fewer than
            :data:`MIN_HISTORY_BARS` non-null bars, or if the returned
            series contains non-finite values. Either case makes the
            realized-vol calculation invalid.
        """
        start = as_of - timedelta(days=_HISTORY_CALENDAR_DAYS)
        prices_df = self.underlying_feed.fetch([underlying], start, as_of)
        series = self._extract_series(prices_df, underlying).dropna()
        if len(series) < MIN_HISTORY_BARS:
            raise ValueError(
                f"synthetic-options: underlying {underlying!r} returned "
                f"{len(series)} usable bars; need at least {MIN_HISTORY_BARS} "
                "to compute trailing 30/60/90-day realized vol"
            )
        prices = series.to_numpy(dtype=float)
        if not np.all(np.isfinite(prices)) or not np.all(prices > 0.0):
            raise ValueError(
                f"synthetic-options: underlying {underlying!r} contains "
                "non-finite or non-positive values; cannot compute log returns"
            )

        spot = float(prices[-1])
        log_returns = np.diff(np.log(prices))
        rv30 = _realized_vol(log_returns, 30)
        rv60 = _realized_vol(log_returns, 60)
        rv90 = _realized_vol(log_returns, 90)

        as_of_date = _to_date(as_of)
        expiries = build_expiry_grid(as_of_date)

        quotes: list[OptionQuote] = []
        for expiry in expiries:
            dte_days = (expiry - as_of_date).days
            T = dte_days / 365.0
            sigma = _select_sigma(dte_days, rv30, rv60, rv90)
            for mult in STRIKE_MULTIPLIERS:
                strike = spot * mult
                for right in (OptionRight.CALL, OptionRight.PUT):
                    quotes.append(
                        self._build_quote(
                            expiry=expiry,
                            spot=spot,
                            strike=strike,
                            T=T,
                            sigma=sigma,
                            right=right,
                        )
                    )

        return OptionChain(
            as_of=as_of,
            underlying=underlying,
            spot=spot,
            quotes=tuple(quotes),
        )

    @staticmethod
    def _extract_series(df: pd.DataFrame, underlying: str) -> pd.Series:
        """Pull the underlying column from the feed-response DataFrame.

        Exact match on ``underlying`` wins. Otherwise the adapter only
        falls back to ``iloc[:, 0]`` when the DataFrame has exactly one
        column — ambiguous OHLCV-shaped inputs raise, because silently
        pricing the chain against, say, an ``Open`` column when the
        feed returned OHLCV would distort every quote without
        surfacing the mistake.
        """
        if underlying in df.columns:
            series = df[underlying]
            return series if isinstance(series, pd.Series) else series.iloc[:, 0]
        if df.shape[1] == 1:
            return df.iloc[:, 0]
        raise ValueError(
            f"synthetic-options: underlying {underlying!r} not in price-feed columns "
            f"{list(df.columns)!r}; cannot disambiguate the price series. "
            "Provide an underlying feed that returns a single close-price column "
            "named after the underlying symbol."
        )

    @staticmethod
    def _build_quote(
        *,
        expiry: date,
        spot: float,
        strike: float,
        T: float,
        sigma: float,
        right: OptionRight,
    ) -> OptionQuote:
        r = DEFAULT_RISK_FREE_RATE
        if right is OptionRight.CALL:
            price = bs.call_price(spot, strike, T, r, sigma)
            delta = bs.call_delta(spot, strike, T, r, sigma)
            theta = bs.call_theta(spot, strike, T, r, sigma)
        else:
            price = bs.put_price(spot, strike, T, r, sigma)
            delta = bs.put_delta(spot, strike, T, r, sigma)
            theta = bs.put_theta(spot, strike, T, r, sigma)
        gamma = bs.gamma(spot, strike, T, r, sigma)
        vega = bs.vega(spot, strike, T, r, sigma)
        # Clamp to zero so a microscopic negative float from BS
        # arithmetic (e.g. 1e-16 for extreme OTM) doesn't trip the
        # ``ge=0.0`` constraint on OptionQuote.bid / ask / last.
        price = max(price, 0.0)
        return OptionQuote(
            expiry=expiry,
            strike=strike,
            right=right,
            bid=price,
            ask=price,
            last=price,
            iv=sigma,
            delta=delta,
            gamma=gamma,
            vega=vega,
            theta=theta,
        )


with contextlib.suppress(ValueError):
    FeedRegistry.register(SyntheticOptionsFeed())

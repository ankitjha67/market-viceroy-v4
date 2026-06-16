"""CFTC COT wide-format adapter (Session 2K).

Variant of :class:`alphakit.data.positioning.cftc_cot_adapter.CFTCCOTAdapter`
that returns a **wide** DataFrame (one column per requested market code) of
net speculator positioning normalised by open interest, satisfying the
multi-feed ``BenchmarkRunner`` contract for informational columns.

Architecture (Session 2K-1, per the Session 2J-2.8 + Session 2K-1
investigation):

* The long-format ``CFTCCOTAdapter`` (registered as ``"cftc-cot"``) remains
  untouched and available for ad-hoc CFTC analysis.
* This adapter is registered as ``"cftc-cot-wide"`` and is the runner-
  compatible variant: ``BenchmarkRunner._resolve_feed`` dispatches every
  ``*_NET_SPEC`` informational symbol to ``"cftc-cot-wide"``.
* Adapter contract uniformity preserved: ``fetch(symbols, start, end,
  frequency) -> pd.DataFrame`` where ``symbols`` are CFTC market codes
  (numeric strings such as ``"067651"`` for NYMEX WTI Physical Crude),
  return is a wide frame indexed by COT report date with one column per
  market code.
* The ``*_NET_SPEC`` ↔ market-code translation lives **runner-side** (the
  strategy declares a ``cftc_market_codes`` mapping; the runner translates
  before this fetch and renames columns back after). The adapter stays
  strategy-agnostic.

Output cell value:

    net_spec(t, market) = (NonComm_long − NonComm_short) / Open_Interest

Bounded in ``[-1, +1]`` (NonComm long and short positions are subsets of
total open interest). NaN-safe: rows with ``open_interest == 0`` (extremely
rare in CFTC reports) produce ``NaN`` rather than ``inf``, and the runner /
strategy finite-only contract surfaces them via ``_validate_feed_values``.

Registers at import time under ``name="cftc-cot-wide"``.
"""

from __future__ import annotations

import contextlib
import io
import zipfile
from datetime import datetime
from typing import cast

import pandas as pd
from alphakit.core.data import OptionChain
from alphakit.core.protocols import raise_chain_not_supported
from alphakit.data.cache import cached_feed
from alphakit.data.errors import OfflineModeError
from alphakit.data.offline import is_offline
from alphakit.data.positioning.cftc_cot_adapter import (
    _COL_DATE,
    _COL_MARKET,
    _COL_NC_LONG,
    _COL_NC_SHORT,
    _COT_URL_TEMPLATE,
    _REQUEST_TIMEOUT_SECONDS,
)
from alphakit.data.rate_limit import acquire as ratelimit_acquire
from alphakit.data.registry import FeedRegistry

_CACHE_TTL_SECONDS = 604_800  # 7 days — COT is weekly.

# The Open Interest column lives at index 7 of ``annual.txt`` and stays
# stable across the 2006-2024 archive (verified by probe). The trailing
# ``(All)`` qualifier distinguishes it from the per-period ``(Old)`` /
# ``(Other)`` Open-Interest columns that follow further in the schema.
_COL_OI = "Open Interest (All)"


class CFTCCOTWideAdapter:
    """Wide-format CFTC COT positioning, runner-compatible."""

    name: str = "cftc-cot-wide"

    @cached_feed(ttl_seconds=_CACHE_TTL_SECONDS)
    def fetch(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        """Return a wide DataFrame of OI-normalised net speculator positioning.

        ``symbols`` are CFTC market codes as zero-padded strings (e.g.
        ``"067651"`` for NYMEX WTI Light Sweet Crude — PHYSICAL, ``"03565B"``
        for NYMEX Henry Hub Natural Gas). ``frequency`` is accepted for
        signature parity but ignored — COT publishes weekly.

        Columns of the returned frame are the requested symbols in the order
        passed (absent codes become explicit ``NaN`` columns via
        ``reindex(columns=symbols)`` — the same defensive pattern as the
        S2J-2.7 yfinance-futures adapter).

        Offline mode (``ALPHAKIT_OFFLINE=1``) raises :class:`OfflineModeError`:
        CFTC positioning is intrinsically real data and has no synthetic
        analogue (same policy as the long-format adapter).
        """
        if is_offline():
            raise OfflineModeError(
                f"{self.name!r} has no offline fixture; set ALPHAKIT_OFFLINE=0 "
                "or mock the adapter in tests."
            )

        try:
            import requests
        except ImportError as exc:
            raise ImportError(
                "requests is required for cftc-cot-wide. Install with: "
                "pip install 'alphakit-data[cftc-cot]'"
            ) from exc

        frames: list[pd.DataFrame] = []
        for year in range(start.year, end.year + 1):
            ratelimit_acquire(self.name)
            url = _COT_URL_TEMPLATE.format(year=year)
            response = requests.get(url, timeout=_REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                inner_name = zf.namelist()[0]
                with zf.open(inner_name) as handle:
                    frames.append(pd.read_csv(handle, dtype={_COL_MARKET: str}, low_memory=False))

        combined = pd.concat(frames, ignore_index=True)
        combined[_COL_DATE] = pd.to_datetime(combined[_COL_DATE], format="%Y-%m-%d")
        combined = combined[combined[_COL_MARKET].isin(symbols)]
        mask = (combined[_COL_DATE] >= pd.Timestamp(start)) & (
            combined[_COL_DATE] <= pd.Timestamp(end)
        )
        combined = combined.loc[mask].copy()

        # OI-normalised net speculator positioning, in [-1, +1]. NaN-safe:
        # rows where ``open_interest == 0`` produce NaN (extremely rare in
        # CFTC reports — guards against a divide-by-zero that would emit
        # ``inf`` and trip the runner's ``_validate_feed_values`` finite check).
        nc_long = combined[_COL_NC_LONG].astype(float)
        nc_short = combined[_COL_NC_SHORT].astype(float)
        oi = combined[_COL_OI].astype(float)
        net_spec_ratio = (nc_long - nc_short) / oi.where(oi != 0, other=pd.NA)

        long_df = pd.DataFrame(
            {
                "date": combined[_COL_DATE].to_numpy(),
                "market_code": combined[_COL_MARKET].to_numpy(),
                "net_spec": net_spec_ratio.to_numpy(),
            }
        )
        wide = long_df.pivot(index="date", columns="market_code", values="net_spec")
        # Lock column order to the request and turn any silently-missing code
        # into an explicit ``NaN`` column (same defensive contract as the
        # yfinance-futures S2J-2.7 reindex).
        wide = wide.reindex(columns=symbols)
        wide.index.name = None
        wide.columns.name = None
        return cast(pd.DataFrame, wide)

    def fetch_chain(self, underlying: str, as_of: datetime) -> OptionChain:
        """CFTC COT has no option chain surface."""
        raise_chain_not_supported(self.name)


with contextlib.suppress(ValueError):
    FeedRegistry.register(CFTCCOTWideAdapter())

"""Polygon.io placeholder adapter (ADR-004).

Phase 2 ships Polygon as a stub so downstream options strategies can
reference ``FeedRegistry.get("polygon")`` today, and Phase 3 can drop
in a real HTTP client without touching any strategy code. No network
calls happen inside this module — both ``fetch`` and ``fetch_chain``
raise.

Error-path contract
-------------------
* ``fetch`` raises :class:`NotImplementedError` unconditionally. The
  Polygon price API is out of scope for Phase 2; equities and futures
  prices come from yfinance/yfinance-futures.
* ``fetch_chain`` branches on ``POLYGON_API_KEY``:
    - **Missing**: raises :class:`PolygonNotConfiguredError` pointing at
      the ``synthetic-options`` feed as the Phase 2 substitute and at
      ``docs/feeds/polygon.md`` for the upgrade roadmap.
    - **Present**: raises :class:`NotImplementedError` pointing at
      ADR-004. A key alone is not enough; the real client ships in
      Phase 3.

The adapter registers with :class:`FeedRegistry` at import time under
``name="polygon"``. Registration is idempotent under pytest's
``--import-mode=importlib`` (the ``ValueError`` on duplicate names is
suppressed).
"""

from __future__ import annotations

import contextlib
import os
from datetime import datetime

import pandas as pd
from alphakit.core.data import OptionChain
from alphakit.data.errors import PolygonNotConfiguredError
from alphakit.data.registry import FeedRegistry


class PolygonAdapter:
    """Placeholder for the real Polygon.io client shipping in Phase 3."""

    name: str = "polygon"

    def fetch(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        """Price fetches are out of scope for the Phase 2 placeholder."""
        raise NotImplementedError(
            "Polygon adapter is a placeholder; use Phase 3+ for real integration. "
            "See docs/adr/004-polygon-placeholder-adapter.md."
        )

    def fetch_chain(self, underlying: str, as_of: datetime) -> OptionChain:
        """Check ``POLYGON_API_KEY`` and refuse both branches in Phase 2.

        Missing key: direct the caller to the synthetic-options feed.
        Present key: the real client is not wired up yet; point at the ADR.
        """
        if not os.environ.get("POLYGON_API_KEY"):
            raise PolygonNotConfiguredError(
                "POLYGON_API_KEY env var not set. Polygon is a placeholder in "
                "Phase 2 — use 'synthetic-options' feed instead. "
                "See docs/feeds/polygon.md."
            )
        raise NotImplementedError(
            "Polygon adapter placeholder. Real integration scoped for Phase 3. "
            "See docs/adr/004-polygon-placeholder-adapter.md."
        )


with contextlib.suppress(ValueError):
    FeedRegistry.register(PolygonAdapter())

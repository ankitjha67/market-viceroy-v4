"""Bridge to `LEAN <https://www.lean.io>`_ — Phase 2+ stub.

LEAN is the open-source engine behind QuantConnect. It has first-class
support for options, futures, crypto derivatives, and streaming data —
everything the vectorised bridges cannot do well. Full integration is a
Phase 2 deliverable (see the master plan, section 5.6).

Until then this module exists as a typed, importable stub so that
:mod:`alphakit.bridges` can advertise the full bridge surface without
forcing a LEAN installation on every user.

Calling :func:`run` raises :class:`NotImplementedError` with a pointer to
the master plan. Design and wiring notes are below for the Phase 2
implementer (left in-code deliberately so they move with the code).

Implementation sketch for Phase 2
---------------------------------
1. Translate the ``StrategyProtocol`` into a LEAN ``QCAlgorithm`` subclass
   at runtime. This means emitting a small ``main.py`` and ``config.json``
   into a temporary LEAN project directory.
2. Map AlphaKit ``AssetClass`` → LEAN ``SecurityType`` (Equity, Option,
   Future, Forex, Crypto).
3. Invoke ``lean backtest`` as a subprocess, capture the resulting
   ``*-backtest.json`` output and parse it into :class:`BacktestResult`.
4. Guard the subprocess call behind a ``docker`` availability check —
   LEAN ships as a Docker image for reproducibility.
"""

from __future__ import annotations

import pandas as pd
from alphakit.core.protocols import BacktestResult, StrategyProtocol

NAME: str = "lean"

_NOT_IMPLEMENTED_MESSAGE: str = (
    "The LEAN bridge is a Phase 2 deliverable and is not yet implemented. "
    "See the AlphaKit master plan, section 5.6, for the implementation plan. "
    "For now, use `alphakit.bridges.vectorbt_bridge` or "
    "`alphakit.bridges.backtrader_bridge`."
)


def run(
    strategy: StrategyProtocol,
    prices: pd.DataFrame,
    *,
    initial_cash: float = 100_000.0,
    commission_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> BacktestResult:
    """Not yet implemented — LEAN integration lands in Phase 2.

    Raises
    ------
    NotImplementedError
        Always. Users are pointed at the vectorbt or backtrader bridge.
    """
    del strategy, prices, initial_cash, commission_bps, slippage_bps
    raise NotImplementedError(_NOT_IMPLEMENTED_MESSAGE)

"""Engine bridges.

Each bridge adapts a :class:`~alphakit.core.protocols.StrategyProtocol`
into a concrete backtesting engine and normalises the engine's native
output back into a :class:`~alphakit.core.protocols.BacktestResult`.

The bridges in this package:

* ``vectorbt_bridge``  — vectorbt (vectorised, fast, daily-ish)
* ``backtrader_bridge`` — backtrader (event-driven, flexible)
* ``lean_bridge``      — LEAN (Phase 2+ stub, raises ``NotImplementedError``)

Bridges that require heavyweight third-party libraries import those
libraries lazily inside ``run()`` so that ``import alphakit.bridges`` is
always cheap and safe.
"""

from __future__ import annotations

__all__ = ["backtrader_bridge", "lean_bridge", "vectorbt_bridge"]

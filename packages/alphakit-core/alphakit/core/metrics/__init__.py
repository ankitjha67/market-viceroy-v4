"""Performance and risk metrics.

All metric functions accept a ``pd.Series`` or ``np.ndarray`` of periodic
returns (not prices) and return a plain ``float``. Annualisation factors
default to ``252`` (daily trading bars) but every function accepts an
override for weekly / monthly / intraday schedules.

None of these functions allocate; all are safe to call inside tight
benchmark loops.
"""

from __future__ import annotations

from alphakit.core.metrics.drawdown import max_drawdown, recovery_time, ulcer_index
from alphakit.core.metrics.returns import (
    calmar_ratio,
    information_ratio,
    sharpe_ratio,
    sortino_ratio,
)
from alphakit.core.metrics.tail import (
    cvar,
    tail_ratio,
    var_historical,
    var_parametric,
)

__all__ = [
    "calmar_ratio",
    "cvar",
    "information_ratio",
    "max_drawdown",
    "recovery_time",
    "sharpe_ratio",
    "sortino_ratio",
    "tail_ratio",
    "ulcer_index",
    "var_historical",
    "var_parametric",
]

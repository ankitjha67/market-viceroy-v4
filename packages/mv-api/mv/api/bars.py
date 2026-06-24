"""Rolling bar-window helper for the continuous paper loop.

The watch loop keeps a ``working_frame`` anchored at launch and merges each newly
fetched batch of bars into it, so the paper session re-runs over a *growing*
window and equity accumulates from the start. Pure / deterministic.
"""

from __future__ import annotations

import polars as pl


def merge_bars(working: pl.DataFrame, new: pl.DataFrame, *, max_bars: int) -> pl.DataFrame:
    """Merge ``new`` bars into ``working``: append, de-dup by ``ts`` (newest wins),
    sort ascending, and cap to the most recent ``max_bars`` rows.

    Newly fetched bars overlap the tail of the window; ``keep="last"`` lets a
    re-fetched (e.g. just-closed) bar replace its earlier provisional copy.
    """
    if working.height == 0:
        combined = new
    elif new.height == 0:
        combined = working
    else:
        combined = pl.concat([working, new], how="vertical")
    combined = combined.unique(subset=["ts"], keep="last").sort("ts")
    if combined.height > max_bars:
        combined = combined.tail(max_bars)
    return combined


__all__ = ["merge_bars"]

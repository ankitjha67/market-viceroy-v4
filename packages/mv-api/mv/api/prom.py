"""Prometheus exposition rendering (QuantDinger-style observability, zero-dep).

Adopted from the QuantDinger review: the platform's posture should be
scrapeable by standard tooling. This renders the deck's own live views in the
Prometheus text exposition format by hand (the format is a few lines of
``# TYPE`` + samples), so no client dependency enters the lock. Values that are
unknown are omitted, never emitted as zero. Pure and unit-tested; the
``/metrics`` route feeds it from the same injected providers the deck reads.
"""

from __future__ import annotations

from typing import Any


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out


def prometheus_text(
    *,
    portfolio: dict[str, Any],
    positions_count: int,
    kill_tripped: bool,
    sources: list[dict[str, Any]],
) -> str:
    """Render the live posture as Prometheus exposition text."""
    lines: list[str] = ["# TYPE mv_up gauge", "mv_up 1"]

    gauges = (
        ("mv_equity_inr", portfolio.get("equity"), "current marked equity in INR"),
        ("mv_day_pnl_inr", portfolio.get("day_pnl"), "day PnL in INR"),
        ("mv_drawdown_ratio", portfolio.get("drawdown"), "drawdown from peak, 0..1"),
        ("mv_peak_equity_inr", portfolio.get("peak_equity"), "running peak equity in INR"),
    )
    for name, raw, help_text in gauges:
        value = _num(raw)
        if value is None:
            continue  # unknown is absent, never zero
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name} {value}")

    lines.append("# TYPE mv_open_positions gauge")
    lines.append(f"mv_open_positions {positions_count}")
    lines.append("# TYPE mv_kill_switch_tripped gauge")
    lines.append(f"mv_kill_switch_tripped {1 if kill_tripped else 0}")

    if sources:
        lines.append("# TYPE mv_source_latency_p50_ms gauge")
        lines.append("# TYPE mv_source_latency_p95_ms gauge")
        lines.append("# TYPE mv_source_quota_burn_pct gauge")
        for row in sources:
            source = _escape_label(str(row.get("source", "unknown")))
            for metric, key in (
                ("mv_source_latency_p50_ms", "latency_p50_ms"),
                ("mv_source_latency_p95_ms", "latency_p95_ms"),
                ("mv_source_quota_burn_pct", "quota_burn_pct"),
            ):
                value = _num(row.get(key))
                if value is not None:
                    lines.append(f'{metric}{{source="{source}"}} {value}')

    return "\n".join(lines) + "\n"


__all__ = ["prometheus_text"]

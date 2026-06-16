"""``mv-smoke`` entry point: run the Phase-0 CCXT->ClickHouse round-trip."""

from __future__ import annotations

from mv.failover.smoke.config import SmokeSettings
from mv.failover.smoke.pipeline import run_smoke


def main() -> None:  # pragma: no cover - thin I/O wrapper, run by integration job / operator
    settings = SmokeSettings()
    result = run_smoke(settings)
    status = "OK" if result.ok else "FAIL"
    print(
        f"[{status}] {result.venue} {result.symbol} {result.timeframe}: "
        f"wrote {result.written} bars, read back {result.read_back}"
    )
    if not result.ok:
        raise SystemExit(1)


if __name__ == "__main__":  # pragma: no cover
    main()

"""Offline GEX runner: real Deribit chain -> gamma profile -> Vol Desk levels.

Fetches the live option book for a currency (keyless public API), computes the
dealer-gamma profile with the Phase-14 GEX engine, prints the levels, and
optionally grades the setup through the Vol Desk rules when the Operator
supplies the structural grade + minervini evidence the chain alone cannot
provide. Offline tool (network), like scripts/run_gate.py — not in per-push CI.

    uv run python scripts/run_gex.py --currency BTC
    uv run python scripts/run_gex.py --currency BTC --grade 9 --minervini 7 --prior-delta 0.45
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - offline I/O tool
    from mv.intelligence.gex.engine import gamma_profile, gamma_row_from_profile
    from mv.intelligence.gex.grading import grade_setup
    from mv.intelligence.sources.deribit import fetch_option_chain

    parser = argparse.ArgumentParser(prog="run-gex", description=__doc__)
    parser.add_argument("--currency", default="BTC", help="Deribit currency (BTC, ETH)")
    parser.add_argument("--grade", type=int, default=None, help="structural grade 0-11 (Operator)")
    parser.add_argument("--minervini", type=int, default=None, help="momentum score (Operator)")
    parser.add_argument("--prior-delta", type=float, default=0.5, help="prior session delta 0..1")
    ns = parser.parse_args(sys.argv[1:] if argv is None else argv)

    chain = fetch_option_chain(ns.currency)
    profile = gamma_profile(chain, as_of=datetime.now(timezone.utc))
    if profile is None:
        raise SystemExit(f"run-gex: no live open interest for {ns.currency}")

    print(f"[gex] {ns.currency} spot {profile.spot:,.0f} | {len(profile.by_strike)} strikes")
    print(f"  zero-gamma flip : {profile.zero_gex:,.0f}")
    print(f"  +GEX magnet (T1): {profile.plus_gex:,.0f}")
    print(f"  put mass (floor): {profile.cotmp:,.0f}")
    print(f"  call mass (T2)  : {profile.cotmc:,.0f}")
    print(f"  dealer delta    : {profile.dealer_delta:.3f} (call share of delta mass)")
    print(f"  net GEX / 1%    : {profile.total_gex:,.0f}")

    if ns.grade is not None and ns.minervini is not None:
        row = gamma_row_from_profile(
            ns.currency,
            profile,
            prior_delta=ns.prior_delta,
            grade=ns.grade,
            minervini=ns.minervini,
        )
        verdict = grade_setup(row)
        print(f"[gex] Vol Desk verdict: {verdict.status.value} — {'; '.join(verdict.reasons)}")
    else:
        print("[gex] pass --grade and --minervini to run the Vol Desk grading on these levels")


if __name__ == "__main__":  # pragma: no cover
    main()

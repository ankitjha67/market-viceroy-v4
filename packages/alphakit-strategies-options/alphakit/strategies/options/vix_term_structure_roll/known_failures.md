# Known failure modes — vix_term_structure_roll

> Phase 2 Session 2F real-data VIX basis trade (^VIX vs VIX=F).
> Whaley 2009 + Simon-Campasano 2014. Differentiated from Phase
> 1 ``vix_term_structure`` (RV proxy) by use of real ^VIX /
> VIX=F data via yfinance passthrough.

## 1. Stress-regime basis-flip whiplash

The VIX basis flips sign rapidly during stress events (e.g.
2018 February, 2020 March): contango → backwardation in 1-3
days. The daily-rebalance signal flips correspondingly,
producing rapid position reversals. Real-world execution
incurs significant slippage on these flip days.

Expected behaviour:
* Drawdown 5-15 % from peak in stress flip windows
* Recovery as the signal stabilises post-event

## 2. Contango whipsaws (no clear regime)

In long quiet-vol regimes the basis can flip slightly above /
below zero on day-to-day noise without representing a true
regime change. Signal flips per noise produce small per-flip
losses (slippage drag) without compensating P&L.

Mitigation in real production: add a basis-threshold buffer
(e.g., ``|basis| > 0.5 vol points``) before flipping. Phase 2
default is ``|basis| > 1e-6`` — sensitive to noise, documented
honestly.

## 3. Cluster overlap

* **`vix_3m_basis`** (Commit 16): ρ ≈ 0.55-0.75. Same
  family (VIX basis trade) with different tenor (^VIX vs
  ^VIX3M instead of ^VIX vs VIX=F).
* **Phase 1 `vix_term_structure`**: ρ ≈ 0.40-0.65 — same
  Simon-Campasano anchor but RV-proxied vs real-data.
* **Phase 1 `vix_roll_short`**: ρ ≈ 0.35-0.60 — similar
  roll-yield direction but XIV-style ETN proxy.

## 4. Differentiation from Phase 1 `vix_term_structure`

This is the **deliberate Phase-1-to-Phase-2 evolution** of the
same trade:

| Aspect | Phase 1 vix_term_structure | Phase 2 vix_term_structure_roll |
|---|---|---|
| VIX source | RV-of-SPY proxy | Real ^VIX index |
| Futures source | RV proxy | Real VIX=F continuous |
| Family | volatility | options |
| Real-data dependency | None (proxy works offline) | yfinance passthrough required |
| Cluster ρ | — | 0.40-0.65 with Phase 1 sibling |

Both ship on main: Phase 1 stays for users without yfinance
access; Phase 2 ships for users who want the real data.

## 5. Standard-benchmark-runner mode

Standard `BenchmarkRunner` provides the universe
`[^VIX, VIX=F]` from `config.yaml`. The runner's
`_fetch_prices` calls yfinance with these symbols. yfinance
returns standard OHLCV for both. Strategy runs end-to-end.

If the runner falls back to the offline fixture generator
(no network or `ALPHAKIT_OFFLINE=1`), synthetic OHLCV is
produced for both tickers. Strategy still runs but the
signal is not anchored on real basis dynamics.

## 6. yfinance ^-prefix passthrough assumption

``^VIX`` is a CBOE index ticker. yfinance's
`yfinance.download()` accepts ^-prefixed tickers without
modification — the prefix is passed through to Yahoo's API
directly. **This passthrough is verified at integration-test
time via a mock that mirrors yfinance's response shape**, not
on real network responses. Real-data shape verification is
deferred to Session 2H benchmark-runner real-feed runs.

If yfinance ever changes its handling of ^-prefixed tickers
(e.g., requires special encoding), this strategy will fail at
the data-fetch step. The failure mode is *crash-in-prices*,
not silent miscomputation — surfaced cleanly.

## 7. VIX=F continuous-contract rollover artefacts

VIX=F is yfinance's continuous front-month VIX future. It
represents a stitched series across calendar contracts; on
monthly rollover dates yfinance may show a small price
discontinuity (back-adjusted vs. front-adjusted convention).

Empirical impact: monthly rollover-day P&L is biased by
~0.5-1 vol points per cycle. Documented for transparency.
Real-feed Polygon (Phase 3) with explicit per-maturity
contracts would resolve.

## 8. Standard substrate caveats

No options chains involved → no skew / bid-ask / volume / OI
substrate caveats from the synthetic-options family.

## 9. yfinance integration verification deferred to Session 2H

Inherited theme: real-data shape verification (yfinance returns
the expected OHLCV columns for ^VIX and VIX=F, no MultiIndex
ambiguity) is deferred to Session 2H benchmark-runner real-feed
runs. Integration tests mock yfinance via the
``YFinanceAdapter.fetch`` mock pattern.

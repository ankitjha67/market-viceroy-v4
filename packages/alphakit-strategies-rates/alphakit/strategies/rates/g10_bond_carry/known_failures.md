# Known failure modes — g10_bond_carry

> Cross-country bond carry has consistent positive expected
> return but periodic large drawdowns when the funding-currency
> basket de-correlates from the high-yield basket. The 2008-09
> GFC and 2022 USD strength are the canonical recent examples.

Cross-sectional dollar-neutral carry on G10 sovereign bond proxies.
Will lose money in the regimes below.

## 1. Funding-currency strength shocks (2008-09, 2022)

The carry trade goes long high-carry currencies' bonds (typically
emerging markets or commodity currencies) and short low-carry
currencies' bonds (typically USD/JPY/CHF). When the low-carry
funding currencies strengthen sharply (flight-to-quality 2008,
USD strength 2022), the FX leg overwhelms the rate-carry leg.

This is documented as the carry-trade "crash risk" — high Sharpe
in normal regimes, large losses in tail events. Asness §V Table III
shows max drawdown of 12-18% on the cross-country bond carry sleeve
during the 2008-09 GFC.

The implementation here trades whatever bond series are passed in
without explicit FX hedging, so it inherits this crash risk
implicitly. Real-feed Session 2H benchmarks with explicit FX-hedged
returns will isolate the pure rate-carry component, which is less
crash-prone but lower-Sharpe.

## 2. Trailing-return proxy vs explicit carry

The strategy uses 3-month trailing return as the carry proxy. This
is correlated with the explicit-yield carry definition (yield minus
short rate) but not identical:

* **Coupon-dominated regime**: carry proxy ≈ yield level (because
  ``Δyield`` is small over 3 months and the trailing return is
  dominated by the coupon).
* **Yield-shift regime**: carry proxy ≈ yield level − duration ×
  ``Δyield`` (the duration component is non-trivial when yields
  move materially).

In yield-shift regimes the proxy ranks countries by *recent
out-performance* rather than *current carry*. This is a momentum-
contaminated carry signal. Real-feed benchmarks with explicit yield
data should use ``carry = yield_10Y − yield_short`` directly.

## 3. Fixture-vs-real-data gap (3-bond US-only proxy)

The default fixture universe is `[TLT, AGG, HYG]` — US-only bond
ETFs across different risk profiles. This is *not* a G10
cross-country panel; it's a fallback that makes the synthetic
benchmark deterministic but obviously biased.

Real-feed Session 2H must use:

* `BWX` — SPDR Barclays International Treasury Bond ETF (G10
  ex-US, FX-unhedged)
* `IGOV` — iShares International Treasury Bond ETF (G10 ex-US)
* `LEMB` — iShares JP Morgan EM Local Currency Bond ETF (EM, FX
  exposure)

Or constructed FX-hedged synthetic returns from FRED's
`IRLTLT01XXM156N` per-country yields and BIS FX rates.

The fixture-based benchmark Sharpe is therefore not representative
of expected real-data Sharpe. Documented prominently here and in
paper.md.

## 4. Cluster correlation with sibling strategies

* `bond_carry_roll` (Phase 1 carry family) — US-only cross-sectional
  carry. Same mechanic, different universe. Expected ρ ≈ 0.3-0.5
  via the US-only sleeve. Both strategies are shipped because they
  trade orthogonal information.
* `bond_tsmom_12_1` and `real_yield_momentum` — single-asset
  momentum. Carry and momentum are positively correlated at the
  country level, so cross-sectional carry overlaps somewhat with
  cross-sectional momentum. Expected ρ ≈ 0.3-0.5.
* `bond_carry_rolldown` (rates family, Commit 6) — time-series
  duration overlay on the slope. Different signal type; expected
  ρ ≈ 0.2-0.3.

None of these cross 0.95.

## 5. Liquidity differentials across G10

Some G10 sovereign bond markets (US, UK, Germany, Japan) are deeply
liquid; others (New Zealand, Australia) are smaller. Bid-ask
spreads and turnover capacity vary. The strategy treats all
countries as equally liquid; in practice the long/short legs have
heterogeneous transaction costs that the bridge's flat
``commission_bps`` doesn't capture.

## 6. Cross-currency funding at extremes

When two currencies' bond yields cross zero in opposite directions
(e.g. JGB at +0.5% and SNB rate at -0.75% pre-2022), the carry
calculation becomes unstable: very small absolute differences amid
large funding-cost differentials. The strategy ranks correctly but
the *magnitude* of the carry is misleading.

## Regime performance (reference, gross of fees, FX-hedged G10 cross-sectional)

| Regime | Window | Sharpe | Max DD |
|---|---|---|---|
| Pre-crisis (2003-07) | 2003-01 – 2007-06 | ~0.7 | −5% |
| GFC (2008-09) | 2008-01 – 2009-12 | ~−0.8 | −18% |
| QE-era recovery (2010-14) | 2010-01 – 2014-12 | ~0.6 | −7% |
| 2022 USD strength | 2022-01 – 2022-12 | ~−1.0 | −12% |
| 2023-25 normalisation | 2023-2025 | ~0.5 | −5% |

(Reference ranges from Asness §V Table III FX-hedged G10 bond
carry; the in-repo benchmark with the US-only fixture proxy is
authoritative for this implementation but materially different
from the FX-hedged G10 paper version —
see [`benchmark_results.json`](benchmark_results.json).)

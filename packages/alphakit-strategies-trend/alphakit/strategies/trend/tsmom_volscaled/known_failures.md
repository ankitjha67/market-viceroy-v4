# Known failure modes — tsmom_volscaled

tsmom_volscaled inherits every failure mode of `tsmom_12_1` (the
underlying economic bet is the same), plus a few that are specific to
the continuous-signal formulation.

## 1. Trendless, range-bound markets (2018)

Same regime as MOP 2012: when no asset classes establish durable trends,
the z-score oscillates around zero and tanh outputs near-zero weights.
Unlike MOP 2012, which still books gross exposure via `sign()`,
tsmom_volscaled correctly *refuses to trade* in low-signal regimes — so
the drawdown in 2018 is **smaller** than tsmom_12_1's, at the cost of
leaving some upside on the table in rapid-reversal environments.

Expected 2018 behaviour:
* Near-zero Sharpe
* ~half of MOP 2012's drawdown

## 2. Sudden regime flips (2022 rate shock, 2023 SVB)

The z-score is slow to turn — it needs several months of new-regime data
to accumulate. During rate shocks the strategy stays long bonds for 1-3
months longer than the MOP sign() variant, which widens the H1-2022
drawdown compared to tsmom_12_1.

Expected behaviour:
* Deeper drawdown than MOP 2012 in the first month of a regime change
* Similar or better recovery 3-6 months after the flip

## 3. Low-dispersion, low-signal regimes

When the cross-sectional dispersion of returns is low (e.g. everything
moves together at low volatility), the z-score saturates weakly and
the strategy runs a much smaller book than MOP 2012. This is
*by design* — it is why HOP (2017) report better Sharpe than MOP
(2012) — but it means the strategy can miss long stretches of quiet
positive returns that sign()-based TSMOM would harvest.

## 4. Hyperparameter sensitivity to `signal_scale`

The default `signal_scale=1.0` is the HOP (2017) convention. Raising
it towards 2-3 makes the signal closer to a hard ±1 (approaching the
MOP 2012 variant); lowering it towards 0.5 softens the book further.
Both changes are valid but change the drawdown profile materially.

## Regime reference

| Regime | tsmom_12_1 | tsmom_volscaled | Comment |
|---|---|---|---|
| GFC 2008 | Sharpe ~1.5 | Sharpe ~1.7 | vol scaling helps in high-vol trends |
| Low-vol 2017 | Sharpe ~0.4 | Sharpe ~0.2 | low z-score → smaller book |
| Range 2018 | Sharpe ~-0.3 | Sharpe ~-0.1 | continuous signal avoids whipsaw |
| Rate shock 2022 H1 | Sharpe ~0.0 | Sharpe ~-0.3 | slower regime flip |
| Reversal 2023 | Sharpe ~-0.5 | Sharpe ~-0.3 | smaller book → smaller loss |

Values are reference ranges from the published CTA and trend-following
literature, not the exact AlphaKit benchmark. See
`benchmark_results.json` for the authoritative numbers once the
Phase 1 benchmark runner is in place.

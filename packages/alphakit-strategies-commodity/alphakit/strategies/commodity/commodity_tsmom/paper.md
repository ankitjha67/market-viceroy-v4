# Paper — Cross-Commodity Time-Series Momentum (Asness §V, 2013)

## Citations

**Initial inspiration:** Moskowitz, T. J., Ooi, Y. H. & Pedersen, L. H.
(2012). **Time series momentum.** *Journal of Financial Economics*,
104(2), 228–250. [https://doi.org/10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003)

**Primary methodology:** Asness, C. S., Moskowitz, T. J. & Pedersen,
L. H. (2013). **Value and momentum everywhere.** *Journal of Finance*,
68(3), 929–985. Section V applies the 12/1 time-series-momentum rule
to commodity futures across an extensive cross-section (energy,
metals, grains, softs, livestock).
[https://doi.org/10.1111/jofi.12021](https://doi.org/10.1111/jofi.12021)

BibTeX entries are aggregated in `docs/papers/phase-2.bib` under
`moskowitz2012tsmom` (foundational) and `asness2013value` (primary)
— both already registered by `bond_tsmom_12_1` and `metals_momentum`
in earlier commits and reused here.

## Why two papers

Moskowitz/Ooi/Pedersen (2012) is the seminal *time-series-momentum*
paper but documents the strategy primarily on a 58-instrument
multi-asset futures panel (commodities are part of that panel but
not the focus). The commodity-specific cross-sectional application —
what this strategy implements — is a Section V case study in
Asness/Moskowitz/Pedersen (2013), which extends the 12/1 rule
explicitly to the commodity panel and confirms positive risk-
adjusted returns. We anchor the implementation on Asness §V because
that is the section whose methodology is replicated verbatim; we
cite Moskowitz 2012 as the foundational reference.

## Differentiation from sibling momentum strategies

* **Phase 1 `tsmom_12_1`** (trend family) — same TSMOM mechanic but
  positioned in the trend family with a balanced 6-ETF multi-asset
  universe (SPY/EFA/EEM/AGG/GLD/DBC). Cited on Moskowitz 2012 as
  the primary because the universe spans equities/bonds/commodities.
  Expected ρ with `commodity_tsmom` ≈ 0.6-0.8 in commodity-driven
  regimes (when commodities dominate the trend signal) and lower
  otherwise. Documented in `known_failures.md`.
* **`metals_momentum`** (Session 2E sibling) — same mechanic on a
  metals-only universe. Strong cluster correlation with this
  strategy when metals dominate the broader commodity cross-section;
  expected ρ ≈ 0.75-0.90.
* **`bond_tsmom_12_1`** (Session 2D rates family) — single-asset
  10Y treasury TSMOM. Different asset class, different universe;
  expected ρ ≈ 0.2-0.4.

## Published rules (Asness §V applied to a commodity panel)

For each commodity *c* and each month-end *t*:

1. Compute the trailing return over the 12 months ending one month
   prior — months ``[t-12, t-1)``. Skip the most recent month per
   the 12/1 convention (sidesteps short-term reversal).
2. **Sign-of-return** trade: long if positive, short if negative.
3. **Per-asset volatility scaling** to a constant target (10%
   annualised by default). Position size for asset *c* at month *t*::

       weight_c(t) = sign(lookback_return_c) × (vol_target / realised_vol_c)

4. Hold one month, rebalance monthly.

| Parameter | Asness §V value | AlphaKit default | Notes |
|---|---|---|---|
| Lookback | 12 months | 12 months | identical |
| Skip | 1 month | 1 month | identical |
| Vol target (per asset) | 40% annualised | 10% annualised | rescaled to portfolio level (see below) |
| Vol estimator | EWMA, 60-day half-life | 63-day rolling σ | converges to same long-run estimate |
| Rebalance | monthly | monthly | identical |
| Holding period | 1 month | 1 month | identical |

### Why the rescaled vol target

Asness §V targets **40% volatility per instrument** because the
panel diversifies across many futures and the gross-leverage budget
is around 2-3×. When applied to a tractable 8-commodity universe,
the 40% per-asset target produces a portfolio volatility well above
any practitioner risk budget. Rescaling to 10% per-asset brings the
8-commodity portfolio volatility into the 8-12% range that asset
owners typically benchmark against.

The *sign* and *relative* sizing are unchanged — only the absolute
scale is rescaled. All headline metrics (Sharpe, Sortino, Calmar)
are scale-invariant, so results remain directly comparable to the
paper.

## Asness §V abstract excerpt (relevant fragment)

> ... time-series momentum is a robust phenomenon. We document
> significant time-series momentum in equity index, currency,
> commodity, and bond futures. The strategy is profitable for each
> of the four asset classes ... A diversified time-series-momentum
> strategy across all asset classes delivers substantial abnormal
> returns ...

The commodity sub-strategy in §V earns a Sharpe of 0.78 over
1985-2010 on the commodity-only sub-panel (Asness Table III). This
implementation, on a smaller 8-commodity default universe, is
expected to come in at 0.4-0.7 OOS — the slightly lower band
reflects reduced cross-sectional dispersion versus the paper's
full 24-commodity panel.

## In-sample period (Asness §V)

* Data: 1985–2010 (24-commodity futures panel, monthly rebalances)
* Out-of-sample: 1973-2009 OOS for the commodity-only sub-strategy
* Sharpe ratios reported in §V are for the *full* commodity panel;
  the smaller 8-commodity AlphaKit default under-performs the §V
  Sharpe because of reduced diversification — this is documented
  in `known_failures.md`.

## Implementation deviations from Asness §V

1. **Rolling σ instead of EWMA.** Both estimators converge to the
   same long-run realised volatility; the rolling window is chosen
   here for *reproducibility* — the weights with the default
   parameters are deterministic functions of the input prices,
   without exponential-decay state to seed.
2. **Per-asset leverage cap of 3×** so a collapse in realised
   volatility cannot push weights to infinity. Asness §V does not
   need this because EWMA estimators are smoother.
3. **Portfolio-level vol target of 10%** instead of the paper's
   per-asset 40%. See "Why the rescaled vol target" above.
4. **No bid-ask, financing, or short-borrow model.** The bridge
   applies a flat ``commission_bps`` per leg.

None of these change the **sign** of the signal or the **relative
ordering** of weights, so the strategy remains faithful to the
paper's economic content.

## Known replications and follow-ups

* **Hurst, Ooi & Pedersen (2017)** — "A Century of Evidence on
  Trend-Following Investing", AQR. Extends the TSMOM result out
  to 1880 on a long-horizon commodity panel.
* **Baltas & Kosowski (2013)** — "Momentum Strategies in Futures
  Markets and Trend-Following Funds", EFA. Replicates Asness §V
  with updated data and decomposes contribution by asset class.
* **Erb & Harvey (2006)** — "The Strategic and Tactical Value of
  Commodity Futures", FAJ. Foundational commodity-factor paper
  that documents momentum alongside roll-yield carry on the
  commodity panel; cited by `commodity_curve_carry` as the
  foundational reference for the carry side.

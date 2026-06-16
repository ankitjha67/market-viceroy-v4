# Strategy paper — inflation_regime_allocation

## Citation

### Primary methodology

Erb, C. B. & Harvey, C. R. (2006). *The Strategic and Tactical Value
of Commodity Futures*. Financial Analysts Journal **62**(2), 69-97.
DOI: [10.2469/faj.v62.n2.4080](https://doi.org/10.2469/faj.v62.n2.4080)

### Foundational paper

Neville, H., Draaisma, T., Funnell, B., Harvey, C. R. & Van Hemert,
O. (2021). *The Best Strategies for Inflationary Times*. Journal of
Portfolio Management Quantitative Special Issue.
DOI: [10.3905/jpm.2021.1.290](https://doi.org/10.3905/jpm.2021.1.290)

## What the papers prove

### Neville et al. 2021 (foundational)

Neville et al. (2021) analyse the performance of 16 asset classes and
strategies across inflationary and disinflationary environments over a
95-year dataset covering 4 developed markets (US, UK, Japan, Germany).
The paper's core findings:

1. **Equity performance is strongly regime-dependent**: real equity
   returns are positive and high in low-inflation environments but
   decline materially as inflation rises above ~4%. In high-inflation
   periods (>4% YoY), equities average negative real returns.

2. **Nominal bonds destroy real value in high inflation**: bond
   duration acts as a liability when inflation is high and rising.
   TLT (long-duration) is the most adversely affected in high-inflation
   regimes.

3. **Gold is an imperfect but important high-inflation hedge**: gold's
   real return is highest in high-inflation environments and near-zero
   in low-inflation environments. It provides optionality in the
   inflation tail.

4. **Commodities are the most reliable high-inflation hedge**: of all
   mainstream asset classes, commodity futures deliver the highest real
   returns in high-inflation environments. The Erb-Harvey (2006)
   tactical timing result confirms this: commodity returns correlate
   positively with the level of inflation.

5. **The ~4% CPI threshold is the key discontinuity**: asset-class
   return rankings are relatively stable below 4% but sharply reverse
   above 4%. The `high_threshold=4.0` default directly maps to this
   empirical discontinuity.

The 3-cell taxonomy (low / moderate / high) is the discrete
implementation of the Neville et al. (2021) regime breakpoints.

### Erb-Harvey 2006 (primary methodology)

Erb & Harvey (2006) document that commodity futures provide:

1. **Strategic value**: a diversified basket of commodity futures
   has historically delivered equity-like returns with low correlation
   to equities and bonds (long-run diversification benefit).

2. **Tactical inflation-timing value**: commodity futures returns
   correlate positively with the **level** of CPI inflation. The
   higher the CPI, the better the commodity futures performance.
   This is distinct from equity inflation hedging (which correlates
   with inflation *changes*, not levels).

The DBC (DB Commodity Index ETF) allocation in the high-inflation
cell implements the Erb-Harvey tactical timing result: the
high-inflation regime is precisely the environment in which DBC
is expected to outperform equity and bonds.

## Implementation

### Informational-column pattern

The strategy reads one FRED informational column:

* **`CPIAUCSL`**: CPI All Urban Consumers, All Items, seasonally
  adjusted. This is an index series (base period: 1982-84 = 100).
  Current value: ~300+. Always strictly positive — satisfies the
  bridge's `order.price > 0` assertion.

The CPI YoY rate is computed *internally* after the publication lag:

```
cpi_yoy = cpi_lagged.pct_change(12) * 100
```

This mirrors the methodology from `growth_inflation_regime_rotation`
(Commit 9), which also uses CPIAUCSL for the inflation dimension. The
key constraint: **lag before YoY** (not YoY then lag) to avoid
lookahead bias — see `known_failures.md` item 2.

### Publication-lag handling

CPIAUCSL is published ~mid-month for the prior month (e.g., the
January CPI is released in mid-February). The `cpi_lag_months=1`
default models this publication timing conservatively.

Both the 12-month YoY lookback AND the regime classification
operate on the lagged series, so the regime at month-end *t* reflects
CPI data available through month *t − 1*.

### 3-cell regime taxonomy

| Regime | CPI YoY condition | Default allocation (SPY/TLT/GLD/DBC) |
|---|---|---|
| **Low** | YoY < 2.0% | 60% / 30% / 5% / 5% |
| **Moderate** | 2.0% ≤ YoY < 4.0% | 40% / 20% / 20% / 20% |
| **High** | YoY ≥ 4.0% | 5% / 5% / 45% / 45% |

### Warm-up and edge cases

The strategy requires `cpi_lag_months + 12` months of CPIAUCSL
history (default: 13 months) before emitting non-zero weights. The
12-month lookback for the YoY computation is the binding constraint.

NaN rows in the lagged CPIAUCSL series (during warm-up) emit zero
weights.

## Expected out-of-sample performance

Neville et al. (2021) Table 1 and Figure 3 document US regime returns
(1926-2020):

* **Low inflation** (CPI < 2%): US equities Sharpe ~0.7; bonds ~0.5.
* **Moderate inflation** (CPI 2-4%): US equities Sharpe ~0.4;
  commodities begin outperforming bonds.
* **High inflation** (CPI > 4%): US equities Sharpe ~−0.3; commodity
  futures Sharpe ~0.6; gold Sharpe ~0.4.

OOS window 2021-2023 (actual high-inflation episode):
* CPI peaked at ~9% in June 2022 (well into the high-inflation cell).
* Strategy: GLD+DBC heavy. GLD −2% (2022, disappointing); DBC +25%
  (2022, inline with Erb-Harvey commodity-inflation correlation).
  Net: moderate positive real return vs. large negative from a 60/40
  benchmark in 2022.

See `benchmark_results.json` for the in-repo synthetic-fixture
benchmark. Real-feed verification is deferred to Phase 2H.

## Cluster correlation with sibling strategies

Predicted pairwise ρ within the Session 2G regime-state group:

* **`growth_inflation_regime_rotation`** (Commit 9): ~0.40-0.60.
  This strategy's CPI YoY inflation dimension directly overlaps with
  Commit 9's inflation dimension (same CPIAUCSL series). The
  differentiation is in the growth dimension (Commit 9 has it; this
  strategy does not).
* **`permanent_portfolio`** (Commit 2): ~0.40-0.60. The PP holds
  25% in each of SPY, TLT, GLD, DBC — all four assets in this
  strategy's universe. In the moderate regime (40/20/20/20), the
  allocations are somewhat similar to PP. The correlation arises
  from the shared 4-asset universe, not the allocation mechanics.
* **`recession_probability_rotation`** (Commit 8): ~0.30-0.50.
* **`yield_curve_regime_allocation`** (Commit 10): ~0.30-0.50.
* **`fed_policy_tilt`** (Commit 11): ~0.30-0.50.

All pairwise ρ values within the Session 2G group sit in the 0.30-0.60
range — well below the ρ > 0.95 dedup-review bar (Phase 2 master
plan §10).

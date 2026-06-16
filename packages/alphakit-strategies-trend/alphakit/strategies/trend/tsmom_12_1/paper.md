# Paper — Time Series Momentum (Moskowitz, Ooi, Pedersen 2012)

## Citation

> Moskowitz, T. J., Ooi, Y. H., & Pedersen, L. H. (2012).
> **Time series momentum.**
> *Journal of Financial Economics*, 104(2), 228–250.
> [https://doi.org/10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003)

BibTeX:

```bibtex
@article{moskowitz2012time,
  title   = {Time series momentum},
  author  = {Moskowitz, Tobias J. and Ooi, Yao Hua and Pedersen, Lasse Heje},
  journal = {Journal of Financial Economics},
  volume  = {104},
  number  = {2},
  pages   = {228--250},
  year    = {2012},
  publisher = {Elsevier},
  doi     = {10.1016/j.jfineco.2011.11.003}
}
```

## Abstract (verbatim from JFE)

> We document significant "time series momentum" in equity index,
> currency, commodity, and bond futures for each of the 58 liquid
> instruments we consider. We find persistence in returns for one to
> 12 months that partially reverses over longer horizons, consistent
> with sentiment theories of initial under-reaction and delayed
> over-reaction. A diversified portfolio of time series momentum
> strategies across all asset classes delivers substantial abnormal
> returns with little exposure to standard asset pricing factors and
> performs best during extreme markets. Examining the trading
> activities of speculators and hedgers, we find that speculators
> profit from time series momentum at the expense of hedgers.

## Published parameters

| Parameter | Paper value | AlphaKit default | Notes |
|---|---|---|---|
| Lookback | 12 months | 12 months | paper "12-1" convention |
| Skip | 1 month | 1 month | same |
| Vol target (per asset) | 40% annualised | 10% annualised | rescaled to portfolio level (see below) |
| Vol estimator | EWMA, 60-day half-life | 63-day rolling σ | converges to same long-run estimate |
| Rebalance | monthly | monthly | same |
| Holding period | 1 month | 1 month | same |

### Why the rescaled vol target

MOP (2012) target **40% volatility *per instrument*** because they size
the book to a gross-leverage budget of roughly 2–3× and diversify across
58 futures. When the strategy is applied to a small multi-asset ETF
universe (6 instruments, as in the reference `config.yaml`) the 40%
per-asset target produces a portfolio volatility far above any
practitioner's risk budget. Rescaling to 10% per-asset brings the
6-asset portfolio volatility into the 8–12% range that most asset
owners benchmark against.

The *sign* and the *relative* sizing are unchanged — it is only the
absolute scale that is rescaled. All headline metrics (Sharpe, Sortino,
Calmar) are scale-invariant, so results remain directly comparable to
the paper.

## In-sample period (paper)

* Data: 1965–2009 (45 years)
* Instruments: 58 liquid futures across 4 asset classes
* Out-of-sample test: January 1985–December 2009 (the paper's "recent"
  subsample)

## Known replications

* **Hurst, Ooi & Pedersen (2017)** — "A Century of Evidence on
  Trend-Following Investing", AQR. Extends MOP out to 1880 and
  reproduces the main findings.
* **Baltas & Kosowski (2013)** — "Momentum Strategies in Futures
  Markets and Trend-Following Funds", EFA. Replicates MOP on an
  updated dataset and decomposes into systematic vs. idiosyncratic
  components.
* **Koijen, Moskowitz, Pedersen & Vrugt (2018)** — "Carry", JFE.
  Uses the MOP time-series-momentum framework as a comparison.

## Implementation deviations from the paper

Documented in [`strategy.py`](strategy.py) near the top. Key items:

1. **Rolling σ** instead of EWMA for reproducibility. Both are unbiased
   estimators of long-run realised vol; the rolling window is
   deterministic in our CI.
2. **Per-asset leverage cap of 3×** so that a collapse in realised
   volatility cannot push weights to infinity. The paper does not need
   this because its EWMA estimator is smoother.
3. **Portfolio-level vol target** of 10% instead of the paper's
   per-asset 40%. See the note above.

None of the deviations change the **sign** or the **relative ordering**
of signals, so the strategy remains faithful to the paper's economic
content.

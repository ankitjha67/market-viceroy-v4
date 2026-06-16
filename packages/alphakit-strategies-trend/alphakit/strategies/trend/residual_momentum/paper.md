# Paper — Residual Momentum (Blitz, Huij & Martens 2011)

## Citation

> Blitz, D., Huij, J. & Martens, M. (2011).
> **Residual momentum.**
> *Journal of Empirical Finance*, 18(3), 506–521.
> [https://doi.org/10.1016/j.jempfin.2011.01.003](https://doi.org/10.1016/j.jempfin.2011.01.003)

```bibtex
@article{blitz2011residual,
  title   = {Residual momentum},
  author  = {Blitz, David and Huij, Joop and Martens, Martin},
  journal = {Journal of Empirical Finance},
  volume  = {18},
  number  = {3},
  pages   = {506--521},
  year    = {2011},
  doi     = {10.1016/j.jempfin.2011.01.003}
}
```

## Abstract

> Conventional momentum strategies exhibit sizeable time-varying
> exposures to the Fama and French factors. In this paper we show
> that these exposures can be reduced by ranking stocks on residual
> stock returns instead of total returns. As a consequence, residual
> momentum earns risk-adjusted profits that are about twice as large
> as those associated with total return momentum; is more consistent
> over time; and is more robust across size and industry subsamples.

## Published parameters

| Parameter | Paper | AlphaKit default |
|---|---|---|
| Factor model | Fama-French 3 factors | **equal-weighted market only** |
| Beta estimation | 36-month rolling | n/a (implicit β=1) |
| Formation | 11 months (12 with 1 skip) | 11 months |
| Rebalance | monthly | monthly |
| Long/short decile | 10% | `top_pct=0.1` |

## Implementation deviations

> **This is a market-hedged simplification, not the full FF3 variant.**

The paper's signal is the cumulative residual from a 3-factor Fama-French
regression. Implementing that faithfully requires access to Ken French's
factor library or a locally-computed SMB / HML panel, neither of which
AlphaKit ships in Phase 1.

For Phase 1 we substitute a **single-factor equal-weighted market**
model (residual = asset return − equal-weighted universe return). This
is a degenerate case of the paper's methodology where every stock is
assumed to have β=1 against the cross-sectional mean.

Practitioner replications (Asness 2014, Novy-Marx 2015) show that the
market-hedged variant captures ~60–70% of the FF3 variant's alpha
improvement over vanilla JT momentum. It is *not* a full replication
and users who need the published numbers should wait for the Phase 4
`residual_momentum_ff3` strategy and the `alphakit.data.factors`
adapter that comes with it.

## In-sample period

* 1926–2009 CRSP US stocks, monthly rebalance.

## Known replications

* Chaves, D. (2012). "Eureka! A Momentum Strategy that Also Works in Japan". SSRN.
* Gutierrez, R. & Prinsky, C. (2007). "Momentum, reversal, and the trading behaviors of institutions". RFS.
* Grundy, B. & Martin, J. S. (2001). "Understanding the nature of the risks and the source of the rewards to momentum investing". RFS.

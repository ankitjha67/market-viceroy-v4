# Book — Algorithmic Trading: Winning Strategies and Their Rationale

> Chan, E.P. (2013). *Algorithmic Trading: Winning Strategies and
> Their Rationale*. Wiley. ISBN 978-1-118-46014-6.

```bibtex
@book{chan2013algorithmic,
  title     = {Algorithmic Trading: Winning Strategies and Their Rationale},
  author    = {Chan, Ernest P.},
  publisher = {Wiley},
  year      = {2013},
  isbn      = {978-1-118-46014-6}
}
```

## Summary

Chan presents a Kalman filter approach to pairs trading that
dynamically estimates the hedge ratio between two cointegrated
assets. Unlike a rolling OLS window, the Kalman filter smoothly
adapts to regime changes and provides a principled Bayesian
framework for updating beliefs about the hedge ratio.

The state-space model treats the hedge ratio as a hidden state
that evolves as a random walk. The observation equation is
price_A = beta * price_B + epsilon. The Kalman gain balances
the transition noise (delta) against the observation noise (ve)
to optimally update beta at each time step.

## Canonical parameters

| Parameter        | Book             | AlphaKit default |
|------------------|------------------|------------------|
| Delta (transition noise) | 1e-4    | 1e-4             |
| Ve (observation noise)   | 1e-3    | 1e-3             |
| Z-score lookback | 20 days          | 20               |
| Entry threshold  | 2.0 sigma        | 2.0              |

## In-sample period

Examples in the book use US equity ETF pairs (EWA/EWC, GLD/GDX).
No formal academic in-sample period.

# Paper — Golden Cross (Brock, Lakonishok, LeBaron 1992)

> Brock, W., Lakonishok, J. & LeBaron, B. (1992). *Simple technical
> trading rules and the stochastic properties of stock returns*.
> *The Journal of Finance*, 47(5), 1731–1764.
> [DOI](https://doi.org/10.1111/j.1540-6261.1992.tb04681.x)

See also [`sma_cross_10_30/paper.md`](../sma_cross_10_30/paper.md) — the
citation is the same but this strategy ships the 50/200 pair (the
"golden cross"/"death cross" configuration most watched on Wall Street).

## Default long_only=True

Unlike the 10/30 variant, 50/200 is typically used as a *binary
equity-exposure switch* rather than a long/short signal. When the
fast SMA is above the slow, be invested; when below, be in cash.
AlphaKit defaults `long_only=True` here to match that convention,
but the long/short mode is available via `long_only=False`.

## In-sample period (same as the 10/30 variant)

* 1897–1986 Dow Jones daily close.

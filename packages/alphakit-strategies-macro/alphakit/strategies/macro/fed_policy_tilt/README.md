# fed_policy_tilt

Federal-policy-tilt 2-cell regime allocation across SPY / TLT / GLD
driven by the direction of the effective federal funds rate
(FEDFUNDS from FRED).

**Family:** macro  
**DOI (primary):** [10.1016/0304-405X(96)00875-X](https://doi.org/10.1016/0304-405X(96)00875-X)  
**DOI (foundational):** [10.3905/joi.2008.17.4.61](https://doi.org/10.3905/joi.2008.17.4.61)

## Signal

The federal funds rate direction is computed as:

```
fed_delta = fedfunds[t-1] - fedfunds[t-1 - lookback_months]
```

where `t-1` reflects the publication lag. A rising delta (`fed_delta > 0`)
classifies as **tightening**; flat or falling classifies as **easing**.

## Regime allocations

| Regime | SPY | TLT | GLD |
|---|---|---|---|
| Easing (rate flat/falling) | 70% | 20% | 10% |
| Tightening (rate rising) | 20% | 60% | 20% |

The equity-heavy assignment to *easing* is the empirical finding of
Jensen-Mercer-Johnson (1996) and Conover et al. (2008): equities
substantially outperform in easing environments; bonds and gold
outperform in tightening.

## Key parameters

| Parameter | Default | Description |
|---|---|---|
| `lookback_months` | 3 | Rate-direction lookback window (months) |
| `fed_lag_months` | 1 | Publication-lag shift applied to FEDFUNDS |

## Known failure modes

See [`known_failures.md`](known_failures.md) for documented risks,
including:
1. Inflationary tightening (2022) — bonds fall with equities
2. Publication-lag forensics (load-bearing)
3. Lookback-window sensitivity
4. ZIRP floor (strategy holds easing weights continuously)
5. Post-tightening reversal lag

## Universe

- **Tradable:** SPY (equity), TLT (long bonds), GLD (gold)
- **Informational:** FEDFUNDS (effective fed funds rate, zero weight)

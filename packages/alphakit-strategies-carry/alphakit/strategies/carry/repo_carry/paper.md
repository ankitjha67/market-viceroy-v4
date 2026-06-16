# Paper — Special Repo Rates

> Duffie, D. (1996). Special Repo Rates. *Journal of Finance*, 51(2),
> 493-526. DOI: 10.1111/j.1540-6261.1996.tb02708.x.

```bibtex
@article{duffie1996special,
  title   = {Special Repo Rates},
  author  = {Duffie, Darrell},
  journal = {Journal of Finance},
  volume  = {51},
  number  = {2},
  pages   = {493--526},
  year    = {1996},
  doi     = {10.1111/j.1540-6261.1996.tb02708.x}
}
```

## Summary

Duffie documents that securities "on special" in the repo market
have lower borrowing rates, creating a carry opportunity.

## Phase 1 proxy

Uses Z-score of price deviation from rolling mean as "specialness"
proxy. True implementation needs repo rate data. See ADR-001.

## Parameters

| Parameter | Default |
|---|---|
| Lookback window | 60 days |
| Z-score threshold | 1.0 |

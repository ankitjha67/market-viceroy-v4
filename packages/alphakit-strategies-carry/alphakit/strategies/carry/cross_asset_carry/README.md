# cross_asset_carry — Cross-Asset Carry Portfolio (KMPV 2018)

> Multi-asset carry aggregation. Risk-adjusted trailing return as
> uniform carry proxy (see ADR-001).

```python
from alphakit.strategies.carry import CrossAssetCarry

strategy = CrossAssetCarry(lookback=63, vol_lookback=63)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).

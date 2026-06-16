# crypto_basis_perp — Perpetual-Spot Basis Mean Reversion

> Fade extreme perp-spot basis levels. Long when basis is unusually
> negative (discount); short when unusually positive (premium).

```python
from alphakit.strategies.meanrev import CryptoBasisPerp

strategy = CryptoBasisPerp(fast_period=5, slow_period=30, threshold=2.0)
```

See [`paper.md`](paper.md) and [`known_failures.md`](known_failures.md).

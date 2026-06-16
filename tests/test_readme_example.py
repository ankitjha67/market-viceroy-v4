"""Smoke test: verify the exact code shown in the README quickstart works.

This test prevents drift between documentation and actual API. If the
README quickstart example changes, this test must be updated to match.
"""

from __future__ import annotations


def test_readme_quickstart() -> None:
    """Run the exact code from the README ## Quickstart section."""
    from alphakit.bridges.vectorbt_bridge import run
    from alphakit.data.fixtures.generator import generate_fixture_prices
    from alphakit.strategies.trend.tsmom_12_1 import TimeSeriesMomentum12m1m

    # 1. Generate a multi-asset price panel
    prices = generate_fixture_prices(symbols=["SPY", "EFA", "EEM", "AGG", "GLD", "DBC"])

    # 2. Instantiate the strategy with default config
    strategy = TimeSeriesMomentum12m1m()

    # 3. Run a vectorized backtest
    result = run(strategy=strategy, prices=prices)

    # 4. Inspect metrics — natural property access as shown in README
    sharpe = result.sharpe
    max_dd = result.max_dd
    ann_ret = result.annualized_return

    assert isinstance(sharpe, float)
    assert isinstance(max_dd, float)
    assert isinstance(ann_ret, float)
    assert max_dd <= 0.0

    # Verify the f-string formatting from the README doesn't crash
    _ = f"Sharpe:        {sharpe:.2f}"
    _ = f"Max DD:        {max_dd:.1%}"
    _ = f"Annual Return: {ann_ret:.1%}"

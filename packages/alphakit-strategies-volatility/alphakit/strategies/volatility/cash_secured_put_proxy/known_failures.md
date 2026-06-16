# Known failure modes — cash_secured_put_proxy

## 1. NOT an options strategy (ADR-002)

## 2. No actual premium collection

## 3. Proxy limitation
Price-derived proxy does not capture the paper's actual mechanism. See docs/deviations.md.

## 4. Tail risk
Volatility strategies have inherent tail risk — large losses can occur in vol spikes.

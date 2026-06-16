# Known failure modes — vix_roll_short

## 1. XIV-style blowup risk (Feb 2018: XIV lost 96% in one day)

## 2. Vol spike can exceed all historical precedent

## 3. Proxy limitation
Price-derived proxy does not capture the paper's actual mechanism. See docs/deviations.md.

## 4. Tail risk
Volatility strategies have inherent tail risk — large losses can occur in vol spikes.

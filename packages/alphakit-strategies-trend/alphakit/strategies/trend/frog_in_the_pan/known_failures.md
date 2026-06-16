# Known failure modes — frog_in_the_pan

## 1. Earnings-season events

Any stock that reports earnings during the formation window will have
a few large jumps on those days, inflating its |ID| score. FIP
**demotes** those stocks even if their earnings were genuinely good
news. This is a known shortcoming of the continuity signal — price
responses to real fundamental surprises look the same as "discrete"
noise.

Mitigation: users who want to trade around earnings should layer the
FIP signal with a post-earnings-announcement-drift filter.

## 2. Low-volume ETF / universe mismatch

ID is sensitive to the day-level granularity of the input data. If
any asset in the universe has intermittent trading (stale closing
prices repeated across multiple days), the pct_pos / pct_neg counts
become unreliable.

## 3. Momentum crashes (shared with all xs-momentum variants)

The 2009 crash hit FIP, JT, residual-momentum, and every other
decile-based cross-sectional momentum strategy. The continuity filter
does not protect against short-side blowups.

## 4. Short lookback sensitivity

The default formation window is 12 months (252 days). Shortening to
3–6 months makes the ID measure noisier (few days in the sample) and
degrades the signal. Users should keep `formation_months` >= 6.

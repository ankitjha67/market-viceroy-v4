# Known failure modes — fx_carry_g10

## 1. Carry crash risk

The FX carry trade is exposed to sudden unwinds ("carry crashes")
when risk aversion spikes. High-yielding currencies can depreciate
10-20% in days during a flight to safety (e.g., JPY carry unwind
in 2008, August 2019).

## 2. Proxy vs. actual carry

This implementation uses trailing returns as a carry proxy, not
actual interest-rate differentials. The proxy conflates carry with
momentum, which can diverge (e.g., a currency appreciating on
capital flows despite low yields).

## 3. Crowded trade

FX carry is one of the most crowded systematic strategies. When
many participants hold the same positions, unwinds are sharper
and recovery is slower.

## 4. Central bank intervention

G10 central banks occasionally intervene in FX markets (e.g., SNB
floor on EURCHF in 2011-2015). Interventions can cause sudden
jumps that overwhelm carry returns.

/** Pure indicator math for chart overlays (display only — never accounting).
 *
 * The strategies compute their own signals on the backend; these are the
 * familiar lines a trader expects to see *on the price* (e.g. the EMA 12/26 the
 * trend strategies cross), computed from the chart's closes. */

/** Exponential moving average; `null` during the warmup (< `span` samples). */
export function ema(values: number[], span: number): (number | null)[] {
  if (span <= 0) return values.map(() => null);
  const k = 2 / (span + 1);
  const out: (number | null)[] = [];
  let prev = 0;
  for (let i = 0; i < values.length; i++) {
    prev = i === 0 ? values[i] : values[i] * k + prev * (1 - k);
    out.push(i + 1 >= span ? prev : null);
  }
  return out;
}

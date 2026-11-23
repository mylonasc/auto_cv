/** Missing/nonfinite analysis is not a zero score. */
export function formatScore(value: number | null | undefined, digits = 1): string {
  return value == null || !Number.isFinite(value) ? 'N/A' : value.toFixed(digits);
}

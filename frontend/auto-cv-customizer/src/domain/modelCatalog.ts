/** Pure settings-dropdown helpers; provider transport stays in services/api. */

export interface ModelOptions {
  options: string[];
  /** True when the saved value is absent from a non-empty provider list. */
  stale: boolean;
}

export function resolveModelOptions(available: string[] | undefined, selected: string): ModelOptions {
  const options = selected && !(available ?? []).includes(selected) ? [selected, ...(available ?? [])] : [...(available ?? [])];
  return { options, stale: options.length > 0 && !(available ?? []).includes(selected) };
}

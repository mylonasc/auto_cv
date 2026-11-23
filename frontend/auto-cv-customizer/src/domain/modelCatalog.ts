/** Pure settings-dropdown helpers; provider transport stays in services/api. */
import type { ModelEntry } from '../types/api.generated';

export interface ModelOptions {
  options: string[];
  /** True when the saved value is absent from a non-empty provider list. */
  stale: boolean;
}

export function resolveModelOptions(available: string[] | undefined, selected: string): ModelOptions {
  const options = selected && !(available ?? []).includes(selected) ? [selected, ...(available ?? [])] : [...(available ?? [])];
  return { options, stale: options.length > 0 && !(available ?? []).includes(selected) };
}

export function formatTokens(count: number | null): string | null {
  if (typeof count !== 'number' || count <= 0) return null;
  if (count >= 1000000) return `${trim(count / 1000000)}M`;
  if (count >= 1000) return `${trim(count / 1000)}K`;
  return `${count}`;
}

function trim(value: number): string {
  return Number.isInteger(value) ? `${value}` : value.toFixed(1).replace(/\.0$/, '');
}

export function formatBytes(bytes: number | null): string | null {
  if (typeof bytes !== 'number' || bytes <= 0) return null;
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${trim(bytes / 1024 ** index)} ${units[index]}`;
}

/** Compact capacity line for tooltips and the selected-model hint. */
export function describeModel(entry: ModelEntry | undefined): string | null {
  if (!entry) return null;
  const parts: string[] = [];
  const context = formatTokens(entry.context_window);
  if (context) {
    const out = formatTokens(entry.max_output_tokens);
    parts.push(out ? `${context} ctx / ${out} out` : `${context} ctx`);
  }
  const size = formatBytes(entry.size_bytes);
  if (size) parts.push(entry.parameters ? `${size} · ${entry.parameters} params` : size);
  else if (entry.parameters) parts.push(`${entry.parameters} params`);
  return parts.length ? parts.join(' · ') : null;
}

export function entryLabel(entry: ModelEntry): string {
  return entry.display || entry.id;
}

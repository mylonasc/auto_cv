import type { WorkingCopySection } from '../types/view';

/** Pure selection: stable score ties, source order retained, stale scores ignored. */
export function applySectionFilter(section: WorkingCopySection): WorkingCopySection {
  const policy = section.filterConfig;
  if (!Number.isInteger(policy.minItemsKeep) || !Number.isInteger(policy.maxItemsKeep) ||
      policy.minItemsKeep < 0 || policy.maxItemsKeep < policy.minItemsKeep ||
      !Number.isFinite(policy.minRelevanceScore) || policy.minRelevanceScore < 0 || policy.minRelevanceScore > 10) {
    throw new Error('Use 0–10 for minimum score and 0 ≤ minimum items ≤ maximum items');
  }
  const score = (index: number) => {
    const item = section.items[index];
    return item.scoredText === item.text ? item.relevanceScore ?? 0 : 0;
  };
  const ranked = section.items.map((_, index) => index).sort((a, b) => score(b) - score(a));
  const selected = new Set<number>();
  for (const index of ranked) {
    if (selected.size < policy.minItemsKeep ||
        (selected.size < policy.maxItemsKeep && score(index) >= policy.minRelevanceScore)) {
      selected.add(index);
    }
  }
  return { ...section, items: section.items.map((item, index) => ({ ...item, kept: selected.has(index) })) };
}

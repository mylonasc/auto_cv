import type { WorkingCopy, WorkingCopyItem, SectionFilterConfig } from '../types/view';
import { applySectionFilter } from './selection.ts';

export function editWorkingItem(copy: WorkingCopy, sectionIndex: number, itemIndex: number, patch: Partial<WorkingCopyItem>): WorkingCopy {
  return { ...copy, sections: copy.sections.map((section, at) => at === sectionIndex ? { ...section,
    items: section.items.map((item, index) => index === itemIndex ? { ...item, ...patch } : item),
  } : section) };
}
export function editWorkingFilter(copy: WorkingCopy, sectionIndex: number, patch: Partial<SectionFilterConfig>): WorkingCopy {
  return { ...copy, sections: copy.sections.map((section, at) => at === sectionIndex ? {
    ...section, filterConfig: { ...section.filterConfig, ...patch },
  } : section) };
}
export function filterWorkingSection(copy: WorkingCopy, sectionIndex: number): WorkingCopy {
  return { ...copy, sections: copy.sections.map((section, at) => at === sectionIndex ? applySectionFilter(section) : section) };
}

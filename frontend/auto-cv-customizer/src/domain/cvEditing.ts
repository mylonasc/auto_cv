import type { CVData, ExperienceSection } from '../types/cv';

export type TextTarget = { type: 'personal' | 'alternative' | 'experience'; sectionIdx?: number; itemIdx?: number };
export function editText(data: CVData, target: TextTarget, text: string): CVData {
  if (target.type === 'personal') return { ...data, personal_statement: text };
  if (target.type === 'alternative') return { ...data,
    alternative_statements: data.alternative_statements.map((item, index) => index === target.itemIdx ? text : item) };
  return { ...data, experience_sections: data.experience_sections.map((section, index) => index === target.sectionIdx ? {
    ...section, text_items: section.text_items.map((item, itemIndex) => itemIndex === target.itemIdx ? text : item),
  } : section) };
}
export function editSection(data: CVData, index: number, patch: Partial<ExperienceSection>): CVData {
  return { ...data, experience_sections: data.experience_sections.map((section, at) => at === index ? { ...section, ...patch } : section) };
}
export function addBullet(data: CVData, sectionIndex: number): CVData {
  return editSection(data, sectionIndex, { text_items: [...data.experience_sections[sectionIndex].text_items, 'New experience bullet...'] });
}
export function removeBullet(data: CVData, sectionIndex: number, itemIndex: number): CVData {
  return editSection(data, sectionIndex, { text_items: data.experience_sections[sectionIndex].text_items.filter((_, at) => at !== itemIndex) });
}

/** Validate canonical editable JSON before applying it to the visual editor. */
export function parseCVJSON(text: string): CVData {
  const value: unknown = JSON.parse(text);
  const object = (item: unknown): item is Record<string, unknown> => !!item && typeof item === 'object' && !Array.isArray(item);
  const strings = (item: unknown) => Array.isArray(item) && item.every(part => typeof part === 'string');
  const template = (item: unknown) => object(item) && typeof item.template_id === 'string' &&
    (item.template_path === null || typeof item.template_path === 'string');
  if (!object(value) || value.schema_version !== 1 || !object(value.candidate) ||
      typeof value.candidate.candidate_id !== 'string' || !value.candidate.candidate_id ||
      typeof value.candidate.full_name !== 'string' || !object(value.candidate.profile) ||
      Object.keys(value.candidate).some(key => !['candidate_id', 'full_name', 'profile'].includes(key)) ||
      typeof value.personal_statement !== 'string' || !strings(value.alternative_statements) ||
      !Array.isArray(value.experience_sections) || !value.experience_sections.every(section =>
        object(section) && ['company', 'position', 'duration'].every(key => typeof section[key] === 'string') && strings(section.text_items)) ||
      !template(value.cv_template) || !object(value.cv_template) || typeof value.cv_template.experience_section_title !== 'string' ||
      !template(value.motivation_letter_template)) {
    throw new Error('Expected canonical CV schema v1: metadata-only candidate, top-level statements/experience and valid templates.');
  }
  return value as unknown as CVData;
}

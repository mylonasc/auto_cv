import Ajv from 'ajv';
import type { CVData, ExperienceSection } from '../types/cv';
import { CV_DATA_SCHEMA } from '../types/api.generated.ts';

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

// Generated from CVData, including nested extra-field rules and backend defaults.
const ajv = new Ajv({ allErrors: true, useDefaults: true, discriminator: true });
const validator = ajv.compile<CVData>(CV_DATA_SCHEMA);
export function parseCVJSON(text: string): CVData {
  const value: unknown = JSON.parse(text);
  if (!validator(value)) {
    throw new Error(`Expected canonical CV schema v1: ${ajv.errorsText(validator.errors, { separator: '; ' })}`);
  }
  return value;
}

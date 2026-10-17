import test from 'node:test';
import assert from 'node:assert/strict';
import type { CVData } from '../../src/types/cv';
import { editText, editSection, addBullet, removeBullet, parseCVJSON } from '../../src/domain/cvEditing.ts';

const source: CVData = {
  schema_version: 1, candidate: { candidate_id: 'test', full_name: 'Candidate', profile: { custom: 'preserve' } },
  personal_statement: 'Original', alternative_statements: ['Alternative'],
  experience_sections: [{ company: 'Example', position: 'Engineer', duration: '2020', text_items: ['One', 'Two'] }],
  cv_template: { template_id: 'default_cv', template_path: null, experience_section_title: 'Experience' },
  motivation_letter_template: { template_id: 'default_motivation_letter', template_path: null },
};
function freeze(value: object) {
  Object.freeze(value);
  Object.values(value).forEach(child => { if (child && typeof child === 'object') freeze(child); });
}
freeze(source);

test('nested source edits are immutable and preserve unrelated metadata/templates', () => {
  const edited = editText(source, { type: 'experience', sectionIdx: 0, itemIdx: 0 }, 'Edited');
  assert.equal(source.experience_sections[0].text_items[0], 'One');
  assert.equal(edited.experience_sections[0].text_items[0], 'Edited');
  assert.notEqual(edited.experience_sections[0], source.experience_sections[0]);
  assert.equal(edited.candidate, source.candidate);
  assert.equal(edited.cv_template, source.cv_template);
  assert.equal(editSection(source, 0, { company: 'Other' }).experience_sections[0].company, 'Other');
  assert.equal(editText(source, { type: 'alternative', itemIdx: 0 }, 'New alternative').alternative_statements[0], 'New alternative');
  assert.equal(editText(source, { type: 'personal' }, 'New statement').personal_statement, 'New statement');
});

test('adding/removing bullets never mutates the original section array', () => {
  assert.deepEqual(addBullet(source, 0).experience_sections[0].text_items, ['One', 'Two', 'New experience bullet...']);
  assert.deepEqual(removeBullet(source, 0, 0).experience_sections[0].text_items, ['Two']);
  assert.deepEqual(source.experience_sections[0].text_items, ['One', 'Two']);
});

test('JSON mode validates structure before returning data for visual editing', () => {
  assert.deepEqual(parseCVJSON(JSON.stringify(source)), source);
  assert.throws(() => parseCVJSON('{broken'));
  for (const patch of [{ schema_version: 2 }, { experience_sections: [{ text_items: [1] }] },
    { candidate: { ...source.candidate, personal_statement: 'duplicate writable content' } },
    { cv_template: {} }, { alternative_statements: [null] }]) {
    assert.throws(() => parseCVJSON(JSON.stringify({ ...source, ...patch })), /canonical CV schema/);
  }
});

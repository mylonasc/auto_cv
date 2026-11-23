import test from 'node:test';
import assert from 'node:assert/strict';
import type { CVData } from '../../src/types/cv';
import { editText, editSection, addBullet, removeBullet, parseCVJSON } from '../../src/domain/cvEditing.ts';
import { editWorkingItem, editWorkingFilter, filterWorkingSection } from '../../src/domain/workingCopyEditing.ts';
import type { WorkingCopy } from '../../src/types/view';

const source: CVData = {
  schema_version: 1, content_format: 'latex', document: null, candidate: { candidate_id: 'test', full_name: 'Candidate', profile: { custom: 'preserve' } },
  personal_statement: 'Original', alternative_statements: ['Alternative'],
  experience_sections: [{ company: 'Example', position: 'Engineer', duration: '2020', text_items: ['One', 'Two'] }],
  cv_template: { template_id: 'default_cv', template_path: null, revision: null, experience_section_title: 'Experience' },
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
    { cv_template: { unexpected: true } }, { alternative_statements: [null] }, { unexpected: true },
    { experience_sections: [{ ...source.experience_sections[0], unexpected: true }] },
    { motivation_letter_template: { ...source.motivation_letter_template, unexpected: true } }]) {
    assert.throws(() => parseCVJSON(JSON.stringify({ ...source, ...patch })), /canonical CV schema/);
  }
});

test('JSON editor uses backend defaults for historical payloads and retains explicit text format', () => {
  const parsed = parseCVJSON(JSON.stringify({ candidate: { candidate_id: 'test' } }));
  assert.equal(parsed.content_format, 'latex');
  assert.deepEqual(parsed.experience_sections, []);
  assert.deepEqual(parsed.candidate.profile, {});
  assert.equal(parsed.cv_template.template_id, 'template2');
  assert.equal(parseCVJSON(JSON.stringify({ ...source, content_format: 'plain_text' })).content_format, 'plain_text');
  assert.throws(() => parseCVJSON(JSON.stringify({ ...source, content_format: 'html' })), /canonical CV schema/);
});

test('generated composition schema preserves typed sections and fills their backend defaults', () => {
  const parsed = parseCVJSON(JSON.stringify({ ...source, cv_template: { ...source.cv_template, revision: 'a'.repeat(64) },
    document: { sections: [
      { kind: 'statement', id: 'about', title: 'About' },
      { kind: 'entries', id: 'projects', title: 'Projects', entries: [{ id: 'one', name: 'Project' }] },
      { kind: 'publications', id: 'papers', title: 'Publications', enabled: false, entries: [{ id: 'paper', title: 'Paper' }] },
    ] } }));
  assert.equal(parsed.document?.format_version, 1);
  assert.equal(parsed.document?.header_latex, '');
  assert.equal(parsed.document?.sections[0].enabled, true);
  const projects = parsed.document?.sections[1];
  assert.equal(projects?.kind, 'entries');
  if (projects?.kind === 'entries') assert.deepEqual(projects.entries[0].technologies, []);
  assert.equal(parsed.document?.sections[2].enabled, false);
  for (const patch of [
    { kind: 'statement', id: 'about', title: 'About', personal_statement: 'duplicate content' },
    { kind: 'unknown', id: 'unknown', title: 'Unknown' },
  ]) assert.throws(() => parseCVJSON(JSON.stringify({ ...parsed, document: { ...parsed.document, sections: [patch] } })), /canonical CV schema/);
});

test('working-copy edit/filter operations are immutable and retain rejected content/score provenance', () => {
  const copy: WorkingCopy = { jobId: 'A', personalStatement: '', contentFormat: 'latex', createdAt: null, updatedAt: null, sections: [{
    id: 'role', company: '', position: '', duration: '', sectionScore: 5, sectionExplanation: null, sectionPostingEvidence: null,
    filterConfig: { minRelevanceScore: 4, minItemsKeep: 0, maxItemsKeep: 5 },
    items: [2, 9].map((score, index) => ({ id: String(index), text: 'Original', originalText: 'Original', scoredText: 'Original',
      relevanceScore: score, explanation: null, postingEvidence: null, kept: true })),
  }] };
  freeze(copy);
  const changed = editWorkingItem(copy, 0, 0, { text: 'Changed' });
  assert.equal(changed.sections[0].items[0].scoredText, 'Original');
  assert.equal(copy.sections[0].items[0].text, 'Original');
  const filtered = filterWorkingSection(editWorkingFilter(changed, 0, { maxItemsKeep: 1 }), 0);
  assert.equal(filtered.sections[0].items.length, 2);
  assert.deepEqual(filtered.sections[0].items.map(item => item.kept), [false, true]);
  assert.ok(copy.sections[0].items.every(item => item.kept));
});

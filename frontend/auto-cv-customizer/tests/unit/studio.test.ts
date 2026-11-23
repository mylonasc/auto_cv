import test from 'node:test';
import assert from 'node:assert/strict';
import { studioDraft } from '../studio-fixture.ts';
import { studioReducer as reduce, initialStudio, same, move, duplicateSection, starterLabel, defaultStarter } from '../../src/domain/studio.ts';
import { httpErrorMessage } from '../../src/services/errors.ts';

test('Studio late load cannot overwrite a newer edit; saves only update captured baselines', () => {
  const draft = studioDraft();
  let state = reduce(initialStudio, { type: 'load', draft, saved: false, edit: 0 });
  const generation = state.generation;
  state = reduce(state, { type: 'cv', cv: { ...draft.cv, personal_statement: 'New edit' } });
  assert.equal(reduce(state, { type: 'load', draft, saved: true, edit: 1 }), state);
  state = reduce(state, { type: 'cvSaved', cv: draft.cv, generation });
  assert.equal(state.draft?.cv.personal_statement, 'New edit');
  assert.ok(!same(state.draft?.cv, state.cvBaseline));
  state = reduce(state, { type: 'package', package: { ...draft.package, name: 'New style' } });
  state = reduce(state, { type: 'templateSaved', value: { package: draft.package, revision: 'b'.repeat(64) }, generation });
  assert.equal(state.draft?.package.name, 'New style');
  assert.ok(!same(state.draft?.package, state.packageBaseline));
  assert.equal(state.draft?.cv.cv_template.revision, 'b'.repeat(64));
  assert.equal(reduce(state, { type: 'cvSaved', cv: draft.cv, generation: generation - 1 }), state);
});

test('ordering is immutable and duplication creates distinct section and entry IDs', () => {
  const array = ['a', 'b', 'c'];
  assert.deepEqual(move(array, 2, -1), ['a', 'c', 'b']);
  assert.deepEqual(array, ['a', 'b', 'c']);
  assert.equal(move(array, 0, -1), array);
  let n = 0;
  const section = { kind: 'entries' as const, id: 'p', title: 'Projects', enabled: true, page_break_before: false,
    entries: [{ id: 'e', name: 'Project', description: '', technologies: [], url: '', bullets: [], enabled: true }] };
  const duplicate = duplicateSection(section, () => `new-${++n}`);
  assert.notEqual(duplicate.id, section.id);
  assert.equal(duplicate.kind, 'entries');
  if (duplicate.kind === 'entries') assert.notEqual(duplicate.entries[0].id, section.entries[0].id);
  assert.throws(() => duplicateSection(studioDraft().cv.document!.sections[0], () => 'no'));
});

test('preview diagnostics retain file and line while bounding displayed output', () => {
  const text = httpErrorMessage(422, { detail: 'Compilation failed', diagnostics: './resume.cls:90: Error\n' + 'x'.repeat(20000) }, 'fallback');
  assert.match(text, /resume.cls:90/);
  assert.ok(text.length < 8300);
});

test('starter selection prefers the wide template and falls back to the registry', () => {
  assert.match(starterLabel('template2'), /Wide/);
  assert.match(starterLabel('default_cv'), /Classic/);
  assert.equal(starterLabel('custom'), 'custom');
  assert.equal(defaultStarter('default_cv', ['default_cv', 'template2']), 'default_cv');
  assert.equal(defaultStarter('gone', ['default_cv', 'template2']), 'template2');
  assert.equal(defaultStarter(undefined, ['default_cv']), 'default_cv');
  assert.equal(defaultStarter(undefined, []), 'default_cv');
});

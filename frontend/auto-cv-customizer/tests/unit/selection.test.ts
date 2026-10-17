import test from 'node:test';
import assert from 'node:assert/strict';
import type { WorkingCopySection } from '../../src/types/view';
import { applySectionFilter } from '../../src/domain/selection.ts';

const section: WorkingCopySection = {
  id: 'role', company: 'Example', position: 'Engineer', duration: '2020', sectionScore: 8,
  sectionExplanation: null, sectionPostingEvidence: null,
  filterConfig: { minItemsKeep: 0, maxItemsKeep: 1, minRelevanceScore: 5 },
  items: ['a', 'b'].map(id => ({ id, text: id, originalText: id, scoredText: id,
    relevanceScore: 8, explanation: null, postingEvidence: null, kept: true })),
};

test('selection is pure, preserves IDs/source order and resolves ties stably', () => {
  const before = structuredClone(section);
  const result = applySectionFilter(section);
  assert.deepEqual(section, before);
  assert.deepEqual(result.items.map(item => [item.id, item.kept]), [['a', true], ['b', false]]);
});

test('edited or unknown scores are not treated as current assessments', () => {
  const edited = structuredClone(section);
  edited.items[0].text = 'Edited a';
  assert.deepEqual(applySectionFilter(edited).items.map(item => item.kept), [false, true]);
  edited.items[1].scoredText = null;
  assert.deepEqual(applySectionFilter(edited).items.map(item => item.kept), [false, false]);
});

test('empty selection and invalid limits are explicit', () => {
  assert.deepEqual(applySectionFilter({ ...section, items: [] }).items, []);
  assert.throws(() => applySectionFilter({ ...section,
    filterConfig: { ...section.filterConfig, minItemsKeep: 2 } }), /minimum items/);
});

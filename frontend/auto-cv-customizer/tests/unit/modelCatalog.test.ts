import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveModelOptions } from '../../src/domain/modelCatalog.ts';

test('live options pass through without a stale warning', () => {
  assert.deepEqual(resolveModelOptions(['a', 'b'], 'a'), { options: ['a', 'b'], stale: false });
});

test('saved values missing from the live list stay selectable and warn', () => {
  assert.deepEqual(resolveModelOptions(['a'], 'retired'), { options: ['retired', 'a'], stale: true });
});

test('empty provider lists never warn and disable the dropdown', () => {
  assert.deepEqual(resolveModelOptions([], ''), { options: [], stale: false });
  assert.deepEqual(resolveModelOptions(undefined, 'kept'), { options: ['kept'], stale: true });
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveModelOptions, formatTokens, formatBytes, describeModel, entryLabel } from '../../src/domain/modelCatalog.ts';
import type { ModelEntry } from '../../src/types/api.generated.ts';

const entry = (overrides: Partial<ModelEntry> = {}): ModelEntry => ({
  id: 'x', display: null, context_window: null, max_output_tokens: null, size_bytes: null, parameters: null, ...overrides,
});

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

test('token and byte counts use compact units', () => {
  assert.equal(formatTokens(1048576), '1M');
  assert.equal(formatTokens(128000), '128K');
  assert.equal(formatTokens(999), '999');
  assert.equal(formatTokens(null), null);
  assert.equal(formatBytes(17741872154), '16.5 GB');
  assert.equal(formatBytes(512), '512 B');
  assert.equal(formatBytes(null), null);
});

test('model descriptions combine context, output, size and parameters', () => {
  assert.equal(describeModel(entry({ context_window: 1048576, max_output_tokens: 65536 })), '1M ctx / 65.5K out');
  assert.equal(describeModel(entry({ size_bytes: 17741872154, parameters: '27.3B' })), '16.5 GB · 27.3B params');
  assert.equal(describeModel(entry({ context_window: 262144 })), '262.1K ctx');
  assert.equal(describeModel(entry()), null);
  assert.equal(describeModel(undefined), null);
});

test('display names fall back to IDs', () => {
  assert.equal(entryLabel(entry({ id: 'a', display: 'A Model' })), 'A Model');
  assert.equal(entryLabel(entry({ id: 'a' })), 'a');
});

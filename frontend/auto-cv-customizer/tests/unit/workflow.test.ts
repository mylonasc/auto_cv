import test from 'node:test';
import assert from 'node:assert/strict';
import { initialWorkflow, workflowReducer as reduce, isDirty } from '../../src/domain/workflow.ts';
import type { ProcessingState, WorkingCopy } from '../../src/types/view';
import { monitorJob } from '../../src/services/jobMonitor.ts';

const job = (id: string, status: ProcessingState['status'] = 'succeeded'): ProcessingState => ({
  jobId: id, status, progress: '', message: '', result: null, jobAnalysis: null, error: null,
});
const copy = (id: string, statement = id): WorkingCopy => ({
  jobId: id, personalStatement: statement, sections: [], createdAt: null, updatedAt: null,
});

test('viewed history and posting preview never replace active execution identity', () => {
  let state = reduce(initialWorkflow, { type: 'started', job: job('running', 'processing') });
  state = reduce(state, { type: 'view', job: job('history') });
  state = reduce(state, { type: 'posting', value: { ...job('unused'), jobId: null } });
  state = reduce(state, { type: 'snapshot', job: job('running') });
  assert.equal(state.viewedJobId, 'history');
  assert.equal(state.activeJobId, null);
  assert.equal(state.jobs.running.status, 'succeeded');
  assert.equal(state.jobs.history.jobId, 'history');
});

test('drafts retain independent edits across selection changes and late loads', () => {
  let state = reduce(initialWorkflow, { type: 'loaded', id: 'A', value: copy('A') });
  state = reduce(state, { type: 'edit', id: 'A', value: copy('A', 'unsaved A') });
  state = reduce(state, { type: 'view', job: job('B') });
  state = reduce(state, { type: 'loaded', id: 'B', value: copy('B') });
  state = reduce(state, { type: 'loaded', id: 'A', value: copy('A', 'late response') });
  assert.equal(state.viewedJobId, 'B');
  assert.equal(state.drafts.A.value.personalStatement, 'unsaved A');
  assert.equal(state.drafts.B.value.personalStatement, 'B');
  assert.ok(isDirty(state.drafts.A));
  assert.ok(!isDirty(state.drafts.B));
  assert.equal(reduce(state, { type: 'edit', id: 'B', value: copy('A') }), state);
});

test('save failure retains dirty draft; reset restores only that job baseline', () => {
  let state = reduce(initialWorkflow, { type: 'loaded', id: 'A', value: copy('A') });
  state = reduce(state, { type: 'edit', id: 'A', value: copy('A', 'edit') });
  state = reduce(state, { type: 'saving', id: 'A' });
  state = reduce(state, { type: 'saveFailed', id: 'A', error: 'disk full' });
  assert.ok(isDirty(state.drafts.A));
  assert.equal(state.drafts.A.error, 'disk full');
  state = reduce(state, { type: 'reset', id: 'A' });
  assert.ok(!isDirty(state.drafts.A));
  assert.equal(state.drafts.A.error, null);
});

test('save response advances baseline without discarding edits made while saving', () => {
  let state = reduce(initialWorkflow, { type: 'loaded', id: 'A', value: copy('A') });
  state = reduce(state, { type: 'edit', id: 'A', value: copy('A', 'submitted') });
  const revision = state.drafts.A.revision;
  state = reduce(state, { type: 'saving', id: 'A' });
  state = reduce(state, { type: 'edit', id: 'A', value: copy('A', 'newer edit') });
  state = reduce(state, { type: 'saved', id: 'A', revision, value: copy('A', 'submitted') });
  assert.equal(state.drafts.A.baseline.personalStatement, 'submitted');
  assert.equal(state.drafts.A.value.personalStatement, 'newer edit');
  assert.ok(isDirty(state.drafts.A));
});

test('matching save response normalizes draft and terminal snapshots cannot regress', () => {
  let state = reduce(initialWorkflow, { type: 'loaded', id: 'A', value: copy('A') });
  state = reduce(state, { type: 'saved', id: 'A', revision: 0, value: copy('A', 'server normalized') });
  assert.ok(!isDirty(state.drafts.A));
  state = reduce(state, { type: 'view', job: job('A') });
  assert.equal(reduce(state, { type: 'snapshot', job: job('A', 'processing') }), state);
});

test('export target remains explicit when another job is viewed', () => {
  let state = reduce(initialWorkflow, { type: 'view', job: job('A') });
  state = reduce(state, { type: 'export', id: 'A' });
  state = reduce(state, { type: 'view', job: job('B') });
  assert.equal(state.exportJobId, 'A');
  assert.equal(state.viewedJobId, 'B');
  assert.equal(reduce(state, { type: 'export', id: 'unknown' }), state);
});

test('rescore advances persisted bullet baseline but preserves newer text and other draft edits', () => {
  const original: WorkingCopy = { ...copy('A'), sections: [{
    id: 'role', company: 'Example', position: 'Engineer', duration: '2020', sectionScore: 8,
    sectionExplanation: null, sectionPostingEvidence: null,
    filterConfig: { minRelevanceScore: 4, minItemsKeep: 1, maxItemsKeep: 5 },
    items: [{ id: 'bullet', text: 'original', scoredText: 'original', originalText: 'original',
      relevanceScore: 9, explanation: null, postingEvidence: null, kept: true }],
  }] };
  let state = reduce(initialWorkflow, { type: 'loaded', id: 'A', value: original });
  const edited = structuredClone(original);
  edited.personalStatement = 'unsaved statement';
  edited.sections[0].items[0].text = 'newer edit';
  state = reduce(state, { type: 'edit', id: 'A', value: edited });
  state = reduce(state, { type: 'rescored', id: 'A', items: { bullet: {
    scoredText: 'submitted edit', relevanceScore: 5, explanation: 'Rescored', postingEvidence: 'Posting',
  } } });
  assert.equal(state.drafts.A.baseline.sections[0].items[0].text, 'submitted edit');
  assert.equal(state.drafts.A.value.sections[0].items[0].text, 'newer edit');
  assert.equal(state.drafts.A.value.sections[0].items[0].scoredText, 'submitted edit');
  assert.equal(state.drafts.A.value.personalStatement, 'unsaved statement');
  assert.ok(isDirty(state.drafts.A));
  assert.equal(original.sections[0].items[0].text, 'original');
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
}

function harness(fetch: () => Promise<ProcessingState>) {
  const listeners = new Map<string, (event: MessageEvent) => void>();
  const snapshots: ProcessingState[] = [];
  let closes = 0;
  let pollsStopped = 0;
  let poll: () => void = () => {};
  const stream = { addEventListener: (type: string, listener: (event: MessageEvent) => void) => listeners.set(type, listener),
    close: () => { closes += 1; }, onerror: null as ((event: Event) => void) | null };
  const stop = monitorJob('A', { stream: () => stream, fetch, decode: value => value as ProcessingState,
    snapshot: value => snapshots.push(value), error: () => {},
    schedule: callback => { poll = callback; return () => { pollsStopped += 1; }; },
  });
  return { stream, snapshots, stop, closes: () => closes, pollsStopped: () => pollsStopped,
    poll: () => poll(), emit: (type: string, value: ProcessingState) => listeners.get(type)?.({ data: JSON.stringify(value) } as MessageEvent) };
}

test('stream terminal event closes ownership and ignores late HTTP/nonmatching events', async () => {
  const pending = deferred<ProcessingState>();
  const monitor = harness(() => pending.promise);
  monitor.emit('job_update', job('B', 'processing'));
  monitor.emit('job_complete', job('A'));
  pending.resolve(job('A', 'processing'));
  await pending.promise;
  assert.equal(monitor.closes(), 1);
  assert.deepEqual(monitor.snapshots.map(value => value.status), ['succeeded']);
});

test('connection error leaves SSE reconnect enabled and polls until terminal', async () => {
  let terminal = false;
  const monitor = harness(async () => job('A', terminal ? 'succeeded' : 'processing'));
  await Promise.resolve();
  monitor.stream.onerror?.(new Event('error'));
  await Promise.resolve();
  assert.equal(monitor.closes(), 0);
  terminal = true;
  monitor.poll();
  await Promise.resolve();
  assert.equal(monitor.closes(), 1);
  assert.equal(monitor.pollsStopped(), 1);
});

test('application unmount closes stream and ignores in-flight HTTP responses', async () => {
  const pending = deferred<ProcessingState>();
  const monitor = harness(() => pending.promise);
  monitor.stop();
  pending.resolve(job('A'));
  await pending.promise;
  assert.equal(monitor.snapshots.length, 0);
  assert.equal(monitor.closes(), 1);
});

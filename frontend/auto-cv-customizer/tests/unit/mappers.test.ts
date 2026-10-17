import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import type * as API from '../../src/types/api.generated';
import { jobToView, resultToView, workingCopyToAPI, workingCopyToView, configToAPI, configToView } from '../../src/services/mappers.ts';
import { DEFAULT_BACKEND_CONFIG } from '../../src/types/api.generated.ts';

// Also validated by Python against the real HTTP and SSE serializers.
const job: API.CVJobResponse = JSON.parse(readFileSync(
  new URL('../../../../tests/fixtures/job-contract.json', import.meta.url), 'utf8',
));

test('HTTP and SSE snapshots preserve identity, analysis, evidence, zero scores and artifacts', () => {
  const view = jobToView(job);
  const streamed = jobToView(JSON.parse(JSON.stringify(job)));
  assert.deepEqual(streamed, view);
  assert.equal(view.jobId, 'contract-job');
  assert.deepEqual(view.jobAnalysis, job.job_analysis);
  assert.equal(view.result?.personal_statement, 'Experienced engineer');
  assert.equal(view.result?.overall_score, 0);
  assert.equal(view.result?.experience_analysis[0].section_score, 0);
  assert.equal(view.result?.experience_analysis[0].posting_evidence, 'Role evidence');
  assert.equal(view.result?.experience_analysis[0].items[0].posting_evidence, 'Bullet evidence');
  assert.equal(view.result?.experience_analysis[0].items[0].kept, false);
  assert.deepEqual(view.result?.artifacts, job.result?.artifacts);
});

for (const status of ['failed', 'cancelled'] as const) {
  test(`${status} snapshot retains terminal identity and error`, () => {
    const view = jobToView({ ...job, status, result: null, error: status === 'failed' ? 'Failed model' : null });
    assert.equal(view.jobId, job.id);
    assert.equal(view.status, status);
    assert.equal(view.result, null);
    assert.equal(view.error, status === 'failed' ? 'Failed model' : null);
  });
}

test('missing metrics stay absent rather than inventing a succeeded result or job ID', () => {
  assert.ok(job.result);
  const view = resultToView({ ...job.result, summary_metrics: null });
  assert.deepEqual(view.summary_metrics, {});
  assert.equal('job_id' in view, false);
  assert.equal('status' in view, false);
});

test('working-copy mapping round-trips all editable and analysis fields', () => {
  const copy: API.WorkingCopy = {
    job_id: job.id, personal_statement: 'Editable statement', created_at: null, updated_at: null,
    sections: [{
      id: 'role-1',
      company: 'Example', position: 'Engineer', duration: '2020', section_score: 0,
      section_explanation: null, section_posting_evidence: 'Role evidence',
      filter_config: { min_relevance_score: 0, min_items_keep: 0, max_items_keep: 6 },
      items: [{ id: 'bullet-1', scored_text: 'Original bullet', text: 'Edited bullet', original_text: 'Original bullet', relevance_score: null,
        explanation: null, posting_evidence: 'Bullet evidence', kept: false }],
    }],
  };
  assert.deepEqual(workingCopyToAPI(workingCopyToView(copy)), copy);
});

test('UI initialization and configuration mapping use generated application defaults', () => {
  const view = configToView(DEFAULT_BACKEND_CONFIG);
  assert.equal(view.analysisModel.model, DEFAULT_BACKEND_CONFIG.analysis_model.model);
  assert.equal(view.rewritePolicy.minRelevanceScore, 4);
  assert.equal(view.outputs.includeCoverLetter, false);
  const roundTrip = configToAPI(view);
  for (const key of ['analysis_model', 'statement_editor_model', 'cover_letter_editor_model'] as const) {
    assert.deepEqual(roundTrip[key], { ...DEFAULT_BACKEND_CONFIG[key], config: {} });
  }
  assert.deepEqual(roundTrip.rewrite_policy, DEFAULT_BACKEND_CONFIG.rewrite_policy);
});

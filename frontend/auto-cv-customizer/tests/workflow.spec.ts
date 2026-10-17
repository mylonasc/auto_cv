import { test, expect, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import type { CVJobResponse, WorkingCopy } from '../src/types/api.generated';
import { DEFAULT_BACKEND_CONFIG } from '../src/types/api.generated';

declare global {
  interface Window { testStreams: Array<EventTarget & { closed: boolean; url: string }> }
}
const fixture: CVJobResponse = JSON.parse(readFileSync(new URL('../../../tests/fixtures/job-contract.json', import.meta.url), 'utf8'));
const makeJob = (id: string): CVJobResponse => ({ ...structuredClone(fixture), id, job_description: `Posting ${id}` });
const makeCopy = (id: string): WorkingCopy => ({ job_id: id, personal_statement: `Statement ${id}`,
  sections: [], created_at: null, updated_at: null });

async function setup(page: Page) {
  const jobs = { A: makeJob('A'), B: makeJob('B') };
  const copies = { A: makeCopy('A'), B: makeCopy('B') };
  const writes: string[] = [];
  const renders: string[] = [];
  const unexpected: string[] = [];
  const loadGates = new Map<string, Promise<void>>();
  const saveGates = new Map<string, Promise<void>>();
  let failSave = false;
  await page.addInitScript(() => {
    localStorage.setItem('auto_cv_saved_jobs_v1', JSON.stringify({ currentJobDescriptionId: 'posting', jobDescriptions: [{
      id: 'posting', title: 'Python Engineer', company: 'Example', content: 'Python role', createdAt: '', updatedAt: '',
    }] }));
    window.testStreams = [];
    Object.defineProperty(window, 'EventSource', { value: class extends EventTarget {
      closed = false;
      onerror = null;
      constructor(public url: string) { super(); window.testStreams.push(this); }
      close() { this.closed = true; }
    } });
  });
  await page.route('**/*', async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== 'http://127.0.0.1:5187') { unexpected.push(url.href); await route.abort(); return; }
    if (!url.pathname.startsWith('/api/')) { await route.continue(); return; }
    const path = url.pathname.replace(/\/$/, '');
    let json: unknown;
    if (path === '/api/v1/config') json = DEFAULT_BACKEND_CONFIG;
    else if (path === '/api/v1/health') json = { status: 'healthy' };
    else if (path === '/api/v1/cv-data/templates') json = { cv_templates: {
      default_cv: 'assets/latex_cv_template_v0.tex', template2: 'assets/latex_cv_template_v2.tex',
    }, motivation_letter_templates: {} };
    else if (path.endsWith('/versions')) json = [{ id: 'master', name: 'Master', last_modified: 0 }];
    else if (path.endsWith('/versions/master')) json = { schema_version: 1, candidate: { candidate_id: 'charilaos_mylonas', full_name: '', profile: {} },
      personal_statement: 'Source statement', alternative_statements: [], experience_sections: [],
      cv_template: { template_id: 'default_cv', template_path: null, experience_section_title: 'Experience' },
      motivation_letter_template: { template_id: 'default_motivation_letter', template_path: null } };
    else if (path === '/api/v1/cv-jobs/job-analysis') json = { job_analysis: { basic_analysis: { skills: 'Preview skills' } } };
    else if (path === '/api/v1/cv-jobs') {
      if (request.method() === 'POST') json = jobs.A;
      else json = Object.values(jobs);
    } else {
      const match = path.match(/^\/api\/v1\/cv-jobs\/(A|B)(\/working-cv|\/render|\/cancel)?$/);
      if (!match) { unexpected.push(`${request.method()} ${path}`); await route.fulfill({ status: 404, json: {} }); return; }
      const id = match[1] as 'A' | 'B';
      if (match[2] === '/working-cv') {
        if (request.method() === 'PUT') {
          writes.push(id);
          if (failSave) { await route.fulfill({ status: 500, json: { detail: 'Save failed' } }); return; }
          copies[id] = request.postDataJSON() as WorkingCopy;
          expect(copies[id].job_id).toBe(id);
          await saveGates.get(id);
        } else await loadGates.get(id);
        json = copies[id];
      } else if (match[2] === '/render') { renders.push(id); json = jobs[id]; }
      else if (match[2] === '/cancel') { jobs[id].status = 'cancelled'; json = jobs[id]; }
      else json = jobs[id];
    }
    await route.fulfill({ json });
  });
  page.on('dialog', dialog => dialog.accept());
  const hold = (map: Map<string, Promise<void>>, id: string) => {
    let release!: () => void;
    map.set(id, new Promise<void>(done => { release = done; }));
    return release;
  };
  return { jobs, copies, writes, renders, unexpected, failSave: (value: boolean) => { failSave = value; },
    holdLoad: (id: string) => hold(loadGates, id), holdSave: (id: string) => hold(saveGates, id) };
}

async function loadHistory(page: Page, id: string) {
  await page.getByRole('button', { name: 'History', exact: true }).click();
  await page.locator('tr').filter({ hasText: `Posting ${id}` }).getByRole('button', { name: 'View Results' }).click();
  await expect(page.getByText(`Viewing job: ${id}`, { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Edit Result Working Copy' }).click();
  await expect(page.getByLabel('Working copy personal statement')).toHaveValue(`Statement ${id}`);
}

test('monitoring survives tab/template changes; history and posting preview do not steal execution', async ({ page }) => {
  const api = await setup(page);
  api.jobs.A.status = 'processing'; api.jobs.A.result = null;
  await page.goto('/');
  await page.getByRole('button', { name: 'Workflow Stages', exact: true }).click();
  await page.getByRole('button', { name: 'Run CV Analysis', exact: true }).click();
  await expect.poll(() => page.evaluate(() => window.testStreams.filter(stream => !stream.closed).length)).toBe(1);
  await page.getByLabel('CV template', { exact: true }).selectOption('template2');
  await expect.poll(() => page.evaluate(() => window.testStreams.filter(stream => !stream.closed).length)).toBe(1);
  await loadHistory(page, 'B');
  await expect(page.getByRole('button', { name: 'Cancel Running Analysis' })).toBeVisible();
  await page.getByRole('button', { name: 'Run Job Analysis Only', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Posting preview' })).toContainText('Preview skills');
  await expect(page.getByLabel('Working copy personal statement')).toHaveValue('Statement B');
  await page.getByRole('button', { name: 'CV Data Editor', exact: true }).click();
  await expect.poll(() => page.evaluate(() => window.testStreams.filter(stream => !stream.closed).length)).toBe(1);
  const completed = makeJob('A');
  api.jobs.A = completed;
  await page.evaluate(job => window.testStreams.find(stream => !stream.closed)?.dispatchEvent(new MessageEvent('job_complete', { data: JSON.stringify(job) })), completed);
  await expect.poll(() => page.evaluate(() => window.testStreams.filter(stream => !stream.closed).length)).toBe(0);
  // Completion must not navigate away from another editor/viewed history result.
  await expect(page.getByText('Source CV version — saving here changes inputs for future analyses, not a result working copy.')).toBeVisible();
  await page.getByRole('button', { name: 'Workflow Stages', exact: true }).click();
  await expect(page.getByLabel('Working copy personal statement')).toHaveValue('Statement B');
  await expect(page.getByRole('button', { name: 'Run CV Analysis', exact: true })).toBeVisible();
  expect(api.unexpected).toEqual([]);
});

test('drafts survive job/tab switching and failed save prevents render', async ({ page }) => {
  const api = await setup(page);
  await page.goto('/');
  await loadHistory(page, 'A');
  await page.getByLabel('Working copy personal statement').fill('Unsaved A');
  await expect(page.getByText('Unsaved changes', { exact: true })).toBeVisible();
  await loadHistory(page, 'B');
  await page.getByLabel('Working copy personal statement').fill('Unsaved B');
  await page.getByRole('button', { name: 'Save Working Copy', exact: true }).click();
  await expect(page.getByText('All changes saved', { exact: true })).toBeVisible();
  expect(api.copies.B.personal_statement).toBe('Unsaved B');
  await page.getByRole('button', { name: 'History', exact: true }).click();
  await page.locator('tr').filter({ hasText: 'Posting A' }).getByRole('button', { name: 'View Results' }).click();
  await page.getByRole('button', { name: 'Edit Result Working Copy' }).click();
  await expect(page.getByLabel('Working copy personal statement')).toHaveValue('Unsaved A');
  api.failSave(true);
  await page.getByRole('button', { name: 'Render CV from Working Copy', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('500');
  expect(api.renders).toEqual([]);
  await expect(page.getByText('Unsaved changes', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Working copy personal statement')).toHaveValue('Unsaved A');
  await page.getByRole('button', { name: 'Reset to saved working copy', exact: true }).click();
  await expect(page.getByLabel('Working copy personal statement')).toHaveValue('Statement A');
  expect(api.writes).toEqual(['B', 'A']);
  expect(api.unexpected).toEqual([]);
});

test('render/export uses the explicitly viewed job, never the newest history result', async ({ page }) => {
  const api = await setup(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'Workflow Stages', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Render CV Artifacts', exact: true })).toBeDisabled();
  await loadHistory(page, 'B');
  await page.getByRole('button', { name: 'Render CV from Working Copy', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Export & Download' })).toBeVisible();
  await expect(page.getByText('Job: B', { exact: true })).toBeVisible();
  expect(api.renders).toEqual(['B']);
  expect(api.writes).toEqual(['B']);
  expect(api.unexpected).toEqual([]);
});

test('late draft response stays keyed to its job after switching results', async ({ page }) => {
  const api = await setup(page);
  const release = api.holdLoad('A');
  await page.goto('/');
  await page.getByRole('button', { name: 'History', exact: true }).click();
  await page.locator('tr').filter({ hasText: 'Posting A' }).getByRole('button', { name: 'View Results' }).click();
  await page.getByRole('button', { name: 'Edit Result Working Copy' }).click();
  await expect(page.getByText('Loading working copy...', { exact: true })).toBeVisible();
  await loadHistory(page, 'B');
  release();
  await expect(page.getByLabel('Working copy personal statement')).toHaveValue('Statement B');
  await loadHistory(page, 'A');
  expect(api.writes).toEqual([]);
  expect(api.unexpected).toEqual([]);
});

test('save completion after switching jobs preserves newer edits and the other draft', async ({ page }) => {
  const api = await setup(page);
  await page.goto('/');
  await loadHistory(page, 'A');
  const release = api.holdSave('A');
  await page.getByLabel('Working copy personal statement').fill('Submitted A');
  await page.getByRole('button', { name: 'Save Working Copy', exact: true }).click();
  await expect(page.getByText('Saving…', { exact: true })).toBeVisible();
  await page.getByLabel('Working copy personal statement').fill('Newer A');
  await loadHistory(page, 'B');
  release();
  await expect(page.getByLabel('Working copy personal statement')).toHaveValue('Statement B');
  await page.getByRole('button', { name: 'History', exact: true }).click();
  await page.locator('tr').filter({ hasText: 'Posting A' }).getByRole('button', { name: 'View Results' }).click();
  await page.getByRole('button', { name: 'Edit Result Working Copy' }).click();
  await expect(page.getByLabel('Working copy personal statement')).toHaveValue('Newer A');
  await expect(page.getByText('Unsaved changes', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Reset to saved working copy', exact: true }).click();
  await expect(page.getByLabel('Working copy personal statement')).toHaveValue('Submitted A');
  expect(api.writes).toEqual(['A']);
  expect(api.unexpected).toEqual([]);
});

test('focused working-copy controls preserve provenance, evidence and selection', async ({ page }) => {
  const api = await setup(page);
  api.copies.A.sections = [{ id: 'role', company: 'Example', position: 'Engineer', duration: '2020',
    section_score: 8, section_explanation: 'Section assessment', section_posting_evidence: 'Role evidence',
    filter_config: { min_relevance_score: 4, min_items_keep: 0, max_items_keep: 1 },
    items: [2, 9].map((score, index) => ({ id: `bullet-${index}`, text: `Bullet text ${index + 1}`, original_text: `Bullet text ${index + 1}`,
      scored_text: `Bullet text ${index + 1}`, relevance_score: score, explanation: 'Bullet assessment', posting_evidence: 'Python evidence', kept: true })),
  }];
  await page.goto('/');
  await loadHistory(page, 'A');
  await page.getByLabel('Bullet 1', { exact: true }).fill('Edited bullet');
  await expect(page.locator('.workcpy-item-score').first()).toContainText('stale');
  await page.getByRole('button', { name: 'Apply Filter', exact: true }).click();
  await expect(page.getByLabel('Keep bullet 1', { exact: true })).not.toBeChecked();
  await expect(page.getByLabel('Keep bullet 2', { exact: true })).toBeChecked();
  await page.getByRole('button', { name: 'Show Analysis', exact: true }).click();
  await expect(page.getByText('Role evidence', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Analysis', exact: true }).first().click();
  await expect(page.getByText('Python evidence', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Save Working Copy', exact: true }).click();
  await expect(page.getByText('All changes saved', { exact: true })).toBeVisible();
  expect(api.copies.A.sections[0].items[0].scored_text).toBe('Bullet text 1');
  expect(api.copies.A.sections[0].items.map(item => item.kept)).toEqual([false, true]);
  expect(api.unexpected).toEqual([]);
});

test('shared modal owns keyboard/focus behavior and editor styles cannot leak outside their feature', async ({ page }) => {
  const api = await setup(page);
  await page.goto('/');
  await loadHistory(page, 'A');
  await page.getByRole('button', { name: 'CV Data Editor', exact: true }).click();
  await expect(page.locator('.editor-tab .header-title')).toHaveCSS('display', 'flex');
  await page.evaluate(() => { const probe = document.createElement('div'); probe.className = 'header-title'; probe.id = 'style-probe'; document.body.append(probe); });
  await expect(page.locator('#style-probe')).toHaveCSS('display', 'block');
  await page.getByRole('button', { name: 'Analysis Results', exact: true }).click();
  await page.getByRole('button', { name: 'Export CV', exact: false }).click();
  const modal = page.getByRole('dialog', { name: 'Export & Download', exact: true });
  await expect(modal).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(modal.getByRole('button', { name: 'Close Export & Download', exact: true })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(modal.getByRole('button', { name: 'Close', exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(modal).not.toBeVisible();
  await expect(page.getByRole('button', { name: 'Export CV', exact: false })).toBeFocused();
  expect(api.unexpected).toEqual([]);
});

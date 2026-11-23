import { test, expect, type Page } from '@playwright/test';
import type { CVData } from '../src/types/cv';
import type { BackendConfig } from '../src/types/api.generated';

const initial: CVData = {
  schema_version: 1,
  content_format: 'latex',
  document: null,
  candidate: {
    candidate_id: 'charilaos_mylonas', full_name: 'Test Candidate',
    profile: { location: 'Test City', custom: 'preserve me' },
  },
  personal_statement: 'Original statement',
  alternative_statements: ['Alternative statement'],
  experience_sections: [{
    company: 'Test Company', position: 'Engineer', duration: '2020-2024',
    text_items: ['Original experience bullet'],
  }],
  cv_template: {
    template_id: 'default_cv', template_path: 'assets/latex_cv_template_v0.tex', revision: null,
    experience_section_title: 'Work Experience',
  },
  motivation_letter_template: {
    template_id: 'default_motivation_letter', template_path: 'assets/cover_letter/CoverLetter_Template.tex',
  },
};

async function isolatedAPI(page: Page, seed: CVData = initial) {
  let stored = structuredClone(seed);
  const additional = new Map<string, CVData>();
  let saveGate: Promise<void> | undefined;
  const unexpected: string[] = [];
  const modelCalls: string[] = [];
  const versionsPath = '/api/v1/cv-data/charilaos_mylonas/versions';
  // Intercept all requests, not only expected endpoints: nothing may reach the
  // Vite backend proxy or an external service if a component adds another call.
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin !== 'http://127.0.0.1:5187') {
      unexpected.push(url.href);
      await route.abort();
      return;
    }
    if (!url.pathname.startsWith('/api/')) {
      await route.continue();
      return;
    }
    let json: unknown;
    if (url.pathname === `${versionsPath}/master`) {
      if (route.request().method() === 'PUT') {
        await saveGate;
        stored = route.request().postDataJSON() as CVData;
        expect(stored.schema_version).toBe(1);
        expect(Object.keys(stored.candidate).sort()).toEqual(['candidate_id', 'full_name', 'profile']);
      }
      json = stored;
    } else if (url.pathname === versionsPath) {
      json = [{ id: 'master', name: 'Master', last_modified: 0 }, ...Array.from(additional.keys(), id => ({ id, name: id, last_modified: 0 }))];
    } else if (url.pathname.startsWith(`${versionsPath}/`)) {
      const id = url.pathname.slice(versionsPath.length + 1);
      if (route.request().method() === 'POST') additional.set(id, route.request().postDataJSON() as CVData);
      if (route.request().method() === 'DELETE') { additional.delete(id); json = { status: 'success' }; }
      else json = additional.get(id);
    } else if (url.pathname === '/api/v1/cv-data/templates') {
      json = {
        cv_templates: { default_cv: 'assets/latex_cv_template_v0.tex', template2: 'assets/latex_cv_template_v2.tex' },
        motivation_letter_templates: { default_motivation_letter: 'assets/cover_letter/CoverLetter_Template.tex' },
      };
    } else if (url.pathname.replace(/\/$/, '') === '/api/v1/config') {
      const model = { provider: 'ollama' as const, model: 'offline-test', config: null };
      json = {
        analysis_model: model, statement_editor_model: model, cover_letter_editor_model: model,
        rewrite_policy: { min_section_items_keep: 1, max_section_items_keep: 5, min_relevance_score: 4 },
        analysis_policy: { max_section_parse_retries: 3 },
        outputs: { render_pdf: true, include_latex: true, include_cover_letter: false, include_scoring_comments: true },
        concurrency_limit: 5,
      } satisfies BackendConfig;
    } else if (url.pathname === '/api/v1/models/available') {
      modelCalls.push(`${route.request().method()} ${url.pathname}${url.search}`);
      json = {
        ollama: { models: [
          { id: 'offline-test', display: null, context_window: 8000, max_output_tokens: null, size_bytes: 512000, parameters: null },
          { id: 'other-model', display: null, context_window: null, max_output_tokens: null, size_bytes: null, parameters: null },
        ], error: null, live: true },
        google: { models: [
          { id: 'models/gemini-3.8-flash', display: 'Gemini 3.8 Flash', context_window: 1048576, max_output_tokens: 65536, size_bytes: null, parameters: null },
        ], error: 'Google model list failed (HTTP 403); showing stable fallback IDs.', live: false },
      };
    } else if (url.pathname === '/api/v1/health') {
      json = { status: 'healthy' };
    } else {
      unexpected.push(`${route.request().method()} ${url.pathname}`);
      await route.fulfill({ status: 404, json: { detail: 'Unexpected API request' } });
      return;
    }
    await route.fulfill({ json });
  });
  page.on('dialog', dialog => dialog.accept());
  return { saved: () => stored, unexpected, additional, modelCalls, holdSave: () => {
    let release!: () => void;
    saveGate = new Promise<void>(resolve => { release = resolve; });
    return release;
  } };
}

test('JSON and visual source modes synchronize; invalid JSON cannot replace or save the CV', async ({ page }) => {
  const api = await isolatedAPI(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'CV Data Editor', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Editing: Master' })).toBeVisible();
  await page.getByRole('button', { name: '{ } JSON Mode', exact: true }).click();
  const edited = structuredClone(initial);
  edited.experience_sections[0].text_items[0] = 'JSON edit retained in visual mode';
  await page.getByLabel('Source CV JSON').fill(JSON.stringify(edited));
  await page.getByRole('button', { name: 'Visual Mode', exact: true }).click();
  await expect(page.getByText('JSON edit retained in visual mode...', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '{ } JSON Mode', exact: true }).click();
  expect(JSON.parse(await page.getByLabel('Source CV JSON').inputValue())).toEqual(edited);
  await page.getByLabel('Source CV JSON').fill('{broken');
  await page.getByRole('button', { name: 'Visual Mode', exact: true }).click();
  await expect(page.getByLabel('Source CV JSON')).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('SyntaxError');
  await page.getByRole('button', { name: 'Save Version' }).click();
  expect(api.saved()).toEqual(initial);
  expect(api.unexpected).toEqual([]);
});

test('Job Input preview saves canonical statements and experience, retaining metadata', async ({ page }) => {
  const api = await isolatedAPI(page);
  await page.goto('/');
  await page.locator('.preview-block .item-text').click();
  await page.locator('.inline-edit textarea').fill('Preview statement edit');
  await page.locator('.inline-actions').getByRole('button', { name: 'Save', exact: true }).click();
  await expect.poll(() => api.saved().personal_statement).toBe('Preview statement edit');
  await page.locator('.preview-section .item-text').click();
  await page.locator('.inline-edit textarea').fill('Preview experience edit');
  await page.locator('.inline-actions').getByRole('button', { name: 'Save', exact: true }).click();
  await expect.poll(() => api.saved().experience_sections[0].text_items[0]).toBe('Preview experience edit');
  await page.reload();
  await expect(page.locator('.preview-block .item-text')).toContainText('Preview statement edit');
  await expect(page.locator('.preview-section .item-text')).toContainText('Preview experience edit');
  expect(api.saved().candidate).toEqual(initial.candidate);
  expect(api.saved().alternative_statements).toEqual(initial.alternative_statements);
  expect(api.saved().cv_template).toEqual(initial.cv_template);
  expect(api.saved().motivation_letter_template).toEqual(initial.motivation_letter_template);
  expect(api.unexpected).toEqual([]);
});

test('visual editor saves statements, alternatives, bullets and template choices in one shape', async ({ page }) => {
  const api = await isolatedAPI(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'CV Data Editor', exact: true }).click();
  await page.getByRole('button', { name: 'Edit master statement', exact: true }).click();
  await page.locator('.edit-textarea').fill('Visual statement edit');
  await page.getByRole('button', { name: 'Apply Edit', exact: true }).click();
  await page.getByRole('button', { name: 'Edit alternative 1', exact: true }).click();
  await page.locator('.edit-textarea').fill('Visual alternative edit');
  await page.getByRole('button', { name: 'Apply Edit', exact: true }).click();
  await page.getByRole('button', { name: 'Edit source bullet 1 in section 1', exact: true }).click();
  await page.locator('.edit-textarea').fill('Visual experience edit');
  await page.getByRole('button', { name: 'Apply Edit', exact: true }).click();
  await page.locator('.sections-panel select').first().selectOption('template2');
  await page.getByRole('button', { name: 'Save Version' }).click();
  await expect.poll(() => api.saved().personal_statement).toBe('Visual statement edit');
  expect(api.saved().alternative_statements).toEqual(['Visual alternative edit']);
  expect(api.saved().experience_sections[0].text_items).toEqual(['Visual experience edit']);
  expect(api.saved().cv_template.template_id).toBe('template2');
  expect(api.saved().cv_template.template_path).toBeNull();
  expect(api.saved().candidate).toEqual(initial.candidate);
  expect(api.saved().motivation_letter_template).toEqual(initial.motivation_letter_template);
  await page.getByRole('button', { name: 'Job Description', exact: true }).first().click();
  await expect(page.locator('.preview-block .item-text')).toContainText('Visual statement edit');
  await expect(page.locator('.preview-section .item-text')).toContainText('Visual experience edit');
  expect(api.unexpected).toEqual([]);
});

test('JSON editor saves canonical metadata and content without duplicate candidate fields', async ({ page }) => {
  const api = await isolatedAPI(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'CV Data Editor', exact: true }).click();
  await page.getByRole('button', { name: '{ } JSON Mode', exact: true }).click();
  const edited = structuredClone(initial);
  edited.personal_statement = 'JSON statement edit';
  edited.alternative_statements = ['JSON alternative edit'];
  edited.experience_sections[0].text_items = ['JSON experience edit'];
  edited.candidate.profile.custom = 'JSON profile edit';
  await page.locator('.json-textarea').fill(JSON.stringify(edited, null, 2));
  await page.getByRole('button', { name: 'Save Version' }).click();
  await expect.poll(() => api.saved()).toEqual(edited);
  await page.getByRole('button', { name: 'Visual Mode', exact: true }).click();
  await expect(page.locator('.personal-statement-group')).toContainText('JSON statement edit');
  await expect(page.locator('.alternatives-list')).toContainText('JSON alternative edit');
  await expect(page.locator('.items-list')).toContainText('JSON experience edit');
  expect(api.unexpected).toEqual([]);
});

test('editing a section title preserves a registry-only template choice', async ({ page }) => {
  const seed = structuredClone(initial);
  seed.cv_template.template_id = 'template2';
  seed.cv_template.template_path = null;
  seed.motivation_letter_template.template_path = null;
  const api = await isolatedAPI(page, seed);
  await page.goto('/');
  await page.getByRole('button', { name: 'CV Data Editor', exact: true }).click();
  await page.getByPlaceholder('Experience section title').fill('Selected Experience');
  await page.getByRole('button', { name: 'Save Version' }).click();
  await expect.poll(() => api.saved().cv_template.experience_section_title).toBe('Selected Experience');
  expect(api.saved().cv_template.template_id).toBe('template2');
  expect(api.saved().cv_template.template_path).toBeNull();
  expect(api.saved().motivation_letter_template.template_path).toBeNull();
  expect(api.unexpected).toEqual([]);
});

test('unapplied source text is protected on tab navigation and analyzing uses the saved version explicitly', async ({ page }) => {
  const api = await isolatedAPI(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'CV Data Editor', exact: true }).click();
  await page.getByRole('button', { name: 'Edit master statement', exact: true }).click();
  await page.getByLabel('Selected source text').fill('Unapplied draft');
  page.removeAllListeners('dialog');
  page.once('dialog', async dialog => { expect(dialog.message()).toContain('unsaved source CV'); await dialog.dismiss(); });
  await page.getByRole('button', { name: 'Workflow Stages', exact: true }).click();
  await expect(page.getByLabel('Selected source text')).toHaveValue('Unapplied draft');
  page.once('dialog', async dialog => { expect(dialog.message()).toContain('saved version'); await dialog.accept(); });
  await page.getByRole('button', { name: 'Analyze Saved Version', exact: false }).click();
  await expect(page.locator('.job-input-tab')).toBeVisible();
  expect(api.saved()).toEqual(initial);
  expect(api.unexpected).toEqual([]);
});

test('invalid JSON drafts are protected and extra template fields cannot enter the visual editor', async ({ page }) => {
  const api = await isolatedAPI(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'CV Data Editor', exact: true }).click();
  await page.getByRole('button', { name: '{ } JSON Mode', exact: true }).click();
  await page.getByLabel('Source CV JSON').fill('{broken');
  page.removeAllListeners('dialog');
  page.once('dialog', dialog => dialog.dismiss());
  await page.getByRole('button', { name: 'Job Description', exact: true }).click();
  await expect(page.getByLabel('Source CV JSON')).toHaveValue('{broken');
  await page.getByLabel('Source CV JSON').fill(JSON.stringify({ ...initial, cv_template: { ...initial.cv_template, typo: 'wrong' } }));
  await page.getByRole('button', { name: 'Visual Mode', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('additional properties');
  expect(api.saved()).toEqual(initial);
  expect(api.unexpected).toEqual([]);
});

test('plain-text format is saved without rewriting authored CV content', async ({ page }) => {
  const api = await isolatedAPI(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'CV Data Editor', exact: true }).click();
  await page.getByLabel('CV text format').selectOption('plain_text');
  await page.getByRole('button', { name: 'Save Version' }).click();
  await expect.poll(() => api.saved().content_format).toBe('plain_text');
  expect(api.saved().personal_statement).toEqual(initial.personal_statement);
  expect(api.saved().experience_sections).toEqual(initial.experience_sections);
  expect(api.unexpected).toEqual([]);
});

test('Job Input inline source edits are protected by the same navigation guard', async ({ page }) => {
  const api = await isolatedAPI(page);
  await page.goto('/');
  await page.locator('.preview-block .item-text').click();
  await page.locator('.inline-edit textarea').fill('Unsaved preview edit');
  page.removeAllListeners('dialog');
  page.once('dialog', dialog => dialog.dismiss());
  await page.getByRole('button', { name: 'CV Data Editor', exact: true }).click();
  await expect(page.locator('.inline-edit textarea')).toHaveValue('Unsaved preview edit');
  expect(api.saved()).toEqual(initial);
  expect(api.unexpected).toEqual([]);
});

test('source navigation waits for saves, while successful version creation/deletion can change selection', async ({ page }) => {
  const api = await isolatedAPI(page);
  const release = api.holdSave();
  await page.goto('/');
  await page.getByRole('button', { name: 'CV Data Editor', exact: true }).click();
  await page.getByLabel('Company 1').fill('Updated company');
  await page.getByRole('button', { name: 'Save Version' }).click();
  await expect(page.getByRole('button', { name: 'Saving...' })).toBeVisible();
  await page.getByRole('button', { name: 'Workflow Stages', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Editing: Master' })).toBeVisible();
  release();
  await expect(page.getByRole('status')).toContainText('Version saved');
  await page.getByTitle('New Version', { exact: true }).click();
  await page.getByPlaceholder('Version name...').fill('New version');
  await page.getByRole('button', { name: 'Create', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Editing: new_version' })).toBeVisible();
  expect(api.additional.get('new_version')?.experience_sections[0].company).toBe('Updated company');
  await page.getByRole('button', { name: 'Delete version new_version', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Editing: Master' })).toBeVisible();
  expect(api.unexpected).toEqual([]);
});

test('preview editing is locked during a source save so a late response cannot discard newer text', async ({ page }) => {
  const api = await isolatedAPI(page);
  const release = api.holdSave();
  await page.goto('/');
  await page.locator('.preview-block .item-text').click();
  await page.locator('.inline-edit textarea').fill('Saved preview text');
  await page.locator('.inline-actions').getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.locator('.inline-edit textarea')).toBeDisabled();
  await expect(page.locator('.inline-actions').getByRole('button', { name: 'Cancel', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Workflow Stages', exact: true }).click();
  await expect(page.locator('.inline-edit textarea')).toHaveValue('Saved preview text');
  release();
  await expect.poll(() => api.saved().personal_statement).toBe('Saved preview text');
  await expect(page.locator('.preview-block .item-text')).toContainText('Saved preview text');
  expect(api.unexpected).toEqual([]);
});

test('settings lists live provider models, surfaces provider errors and warns on retired IDs', async ({ page }) => {
  const api = await isolatedAPI(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'Settings' }).click();
  await expect(page.getByRole('heading', { name: 'Backend Configuration' })).toBeVisible();
  const analysisModels = page.getByLabel('Available Models:').first();
  await expect(analysisModels.locator('option[value="other-model"]')).toHaveCount(1);
  await expect(analysisModels.locator('option[value="offline-test"]')).toHaveCount(1);
  await expect(page.getByText('live list')).toHaveCount(2);
  await expect(page.getByText('Selected: 8K ctx · 500 KB.').first()).toBeVisible();
  await page.getByLabel('Provider:').first().selectOption('google');
  await expect(analysisModels.locator('option[value="models/gemini-3.8-flash"]')).toHaveCount(1);
  await expect(analysisModels).toContainText('Gemini 3.8 Flash');
  await analysisModels.selectOption('models/gemini-3.8-flash');
  await expect(page.getByText('Selected: 1M ctx / 65.5K out.').first()).toBeVisible();
  await expect(page.getByText(/Provider list unavailable: Google model list failed/).first()).toBeVisible();
  await page.getByLabel('Custom Model:').first().fill('models/dead-preview');
  await expect(page.getByText(/may be retired/).first()).toBeVisible();
  await page.getByRole('button', { name: 'Refresh model lists' }).click();
  await expect.poll(() => api.modelCalls.length).toBe(2);
  expect(api.modelCalls[1]).toContain('refresh=true');
  expect(api.unexpected).toEqual([]);
});

import { test, expect, type Page } from '@playwright/test';
import type { CVData } from '../src/types/cv';

const initial: CVData = {
  schema_version: 1,
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
    template_id: 'default_cv', template_path: 'assets/latex_cv_template_v0.tex',
    experience_section_title: 'Work Experience',
  },
  motivation_letter_template: {
    template_id: 'default_motivation_letter', template_path: 'assets/cover_letter/CoverLetter_Template.tex',
  },
};

async function isolatedAPI(page: Page, seed: CVData = initial) {
  let stored = structuredClone(seed);
  const unexpected: string[] = [];
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
        stored = route.request().postDataJSON() as CVData;
        expect(stored.schema_version).toBe(1);
        expect(Object.keys(stored.candidate).sort()).toEqual(['candidate_id', 'full_name', 'profile']);
      }
      json = stored;
    } else if (url.pathname === versionsPath) {
      json = [{ id: 'master', name: 'Master', last_modified: 0 }];
    } else if (url.pathname === '/api/v1/cv-data/templates') {
      json = {
        cv_templates: { default_cv: 'assets/latex_cv_template_v0.tex', template2: 'assets/latex_cv_template_v2.tex' },
        motivation_letter_templates: { default_motivation_letter: 'assets/cover_letter/CoverLetter_Template.tex' },
      };
    } else if (url.pathname.replace(/\/$/, '') === '/api/v1/config') {
      json = {};
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
  return { saved: () => stored, unexpected };
}

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
  await page.locator('.personal-statement-group .item-edit-card').first().click();
  await page.locator('.edit-textarea').fill('Visual statement edit');
  await page.getByRole('button', { name: 'Apply Edit', exact: true }).click();
  await page.locator('.alternatives-list .item-edit-card').first().click();
  await page.locator('.edit-textarea').fill('Visual alternative edit');
  await page.getByRole('button', { name: 'Apply Edit', exact: true }).click();
  await page.locator('.items-list .item-edit-card').first().click();
  await page.locator('.edit-textarea').fill('Visual experience edit');
  await page.getByRole('button', { name: 'Apply Edit', exact: true }).click();
  await page.locator('.sections-panel select').first().selectOption('template2');
  await page.getByRole('button', { name: 'Save Version' }).click();
  await expect.poll(() => api.saved().personal_statement).toBe('Visual statement edit');
  expect(api.saved().alternative_statements).toEqual(['Visual alternative edit']);
  expect(api.saved().experience_sections[0].text_items).toEqual(['Visual experience edit']);
  expect(api.saved().cv_template.template_id).toBe('template2');
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

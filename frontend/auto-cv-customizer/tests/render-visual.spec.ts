import { test, expect, type APIRequestContext, type Page, type TestInfo } from '@playwright/test';

/** Opt-in visual E2E: real Studio preview/report compiles through the backend.
 * Run only with a real backend on :8005 backed by a temporary data root
 * (see playwright.visual.config.ts). Never runs under `test:cv`.
 */

const CANDIDATE = 'charilaos_mylonas';

function seedCV(starter: string) {
  return {
    schema_version: 1,
    content_format: 'latex',
    document: null,
    candidate: { candidate_id: CANDIDATE, full_name: 'Visual Check', profile: {} },
    personal_statement: 'Synthetic statement for visual review.',
    alternative_statements: [],
    experience_sections: [{
      company: 'Acme Corp', position: 'Senior Engineer', duration: '2020 -- 2024',
      text_items: ['Led Python delivery across a multi-team programme with a deliberately long bullet that wraps across the row to expose indentation, wrapping and overflow behaviour.'],
    }],
    cv_template: { template_id: starter, template_path: null, revision: null, experience_section_title: 'Work Experience' },
    motivation_letter_template: { template_id: 'default_motivation_letter', template_path: null },
  };
}

async function seedMaster(request: APIRequestContext, starter: string) {
  const url = `/api/v1/cv-data/${CANDIDATE}/versions/master`;
  const existing = await request.get(url);
  if (existing.status() === 404) {
    expect(await (await request.post(url, { data: seedCV(starter) })).json()).toBeDefined();
  } else {
    expect((await request.put(url, { data: seedCV(starter) })).status()).toBe(200);
  }
}

async function openStudio(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Template Studio', exact: true }).last().click();
  await expect(page.getByRole('heading', { name: 'Template Studio' })).toBeVisible();
}

async function loadStarter(page: Page, starter: string) {
  await page.getByLabel('Starter template', { exact: true }).selectOption(starter);
  await page.getByRole('button', { name: 'Load / import draft' }).click();
  await expect(page.getByText('CV: unsaved · Template: unsaved')).toBeVisible({ timeout: 60000 });
}

async function attachPDF(request: APIRequestContext, testInfo: TestInfo, starter: string) {
  const imported = await request.post('/api/v1/template-studio/import', {
    data: { cv: seedCV(starter), template_id: `visual-${starter}`, name: `Visual ${starter}`, source_template: starter },
  });
  expect(imported.status()).toBe(200);
  const draft = await imported.json();
  const preview = await request.post('/api/v1/template-studio/preview', { data: draft, timeout: 90000 });
  expect(preview.status()).toBe(200);
  const pdf = await preview.body();
  expect(pdf.subarray(0, 5).toString()).toBe('%PDF-');
  await testInfo.attach(`studio-${starter}.pdf`, { body: pdf, contentType: 'application/pdf' });
}

for (const starter of ['template2', 'default_cv']) {
  test(`Studio visual: ${starter} previews, reports zero overlaps and saves a review PDF`, async ({ page, request }, testInfo) => {
    await seedMaster(request, starter);
    await openStudio(page);
    await expect(page.getByLabel('Starter template', { exact: true })).toContainText('template2');
    await expect(page.getByLabel('Starter template', { exact: true })).toContainText('default_cv');
    await loadStarter(page, starter);
    await page.getByRole('button', { name: 'Preview PDF', exact: true }).click();
    await expect(page.getByTitle('Studio PDF preview', { exact: true }))
      .toHaveAttribute('src', /^blob:/, { timeout: 90000 });
    await page.getByRole('button', { name: 'Check layout quality', exact: true }).click();
    const status = page.getByRole('status').filter({ hasText: 'Layout quality' });
    await expect(status).toContainText('0 overlaps', { timeout: 90000 });
    await expect(status).toContainText('0 outside page');
    await attachPDF(request, testInfo, starter);
  });
}

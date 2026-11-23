import { test, expect, type Page } from '@playwright/test';
import { studioDraft } from './studio-fixture';
import { DEFAULT_BACKEND_CONFIG, type StudioDraft } from '../src/types/api.generated';

async function setup(page: Page) {
  const draft = studioDraft();
  const unexpected: string[] = [];
  let saved: StudioDraft | null = null;
  const previews: StudioDraft[] = [];
  let previewGate: Promise<void> | undefined;
  let previewError = false;
  let conflict = false;
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin !== 'http://127.0.0.1:5187') { unexpected.push(url.href); return route.abort(); }
    if (!url.pathname.startsWith('/api/')) return route.continue();
    const path = url.pathname;
    if (path.endsWith('/health')) return route.fulfill({ json: { status: 'healthy' } });
    if (path.endsWith('/config')) return route.fulfill({ json: DEFAULT_BACKEND_CONFIG });
    if (path.endsWith('/cv-data/templates')) return route.fulfill({ json: { cv_templates: { default_cv: 'builtin.tex' }, motivation_letter_templates: {} } });
    if (path.endsWith('/versions')) return route.fulfill({ json: [{ id: 'master', name: 'Master', last_modified: 0 }] });
    if (path.endsWith('/versions/master')) return route.fulfill({ json: { ...draft.cv, document: null, cv_template: { ...draft.cv.cv_template, revision: null, template_id: 'default_cv' } } });
    if (path.endsWith('/template-studio/import')) return route.fulfill({ json: draft });
    if (path.endsWith('/template-studio/preview')) {
      previews.push(route.request().postDataJSON());
      await previewGate;
      if (previewError) return route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify({ detail: 'XeLaTeX compilation failed.', diagnostics: './resume.cls:90: Undefined control sequence.' }) });
      return route.fulfill({ contentType: 'application/pdf', headers: { 'X-Preview-Input': 'c'.repeat(64) }, body: Buffer.from('%PDF-1.4\n% offline placeholder\n') });
    }
    if (path.endsWith('/template-studio/packages') && route.request().method() === 'POST') {
      if (conflict) return route.fulfill({ status: 409, json: { detail: 'Template changed; reload the saved revision before saving' } });
      return route.fulfill({ json: { revision: 'b'.repeat(64), package: route.request().postDataJSON().package } });
    }
    if (path.endsWith('/versions/studio') && route.request().method() === 'POST') {
      saved = { cv: route.request().postDataJSON(), package: draft.package };
      return route.fulfill({ json: saved.cv });
    }
    unexpected.push(`${route.request().method()} ${path}`);
    return route.fulfill({ status: 404, json: { detail: 'Unexpected' } });
  });
  page.on('dialog', d => d.accept());
  await page.goto('/');
  await page.getByRole('button', { name: 'Template Studio', exact: true }).last().click();
  await page.getByRole('button', { name: 'Load / import draft' }).click();
  await expect(page.getByText('CV: unsaved · Template: unsaved')).toBeVisible();
  return { unexpected, previews, saved: () => saved, conflict: () => { conflict = true; }, failPreview: () => { previewError = true; }, holdPreview: () => {
    let release!: () => void;
    previewGate = new Promise<void>(resolve => { release = resolve; });
    return release;
  } };
}

test('Studio edits, order, inclusion, raw files and separate saves survive tab navigation', async ({ page }) => {
  const api = await setup(page);
  await page.getByText('Statement and experience content', { exact: true }).click();
  await page.getByLabel('Personal statement', { exact: true }).fill('Unsaved Studio statement');
  await page.getByRole('button', { name: 'Add entries', exact: true }).click();
  const section = page.getByTestId('studio-section').last();
  await section.locator('summary').click();
  await section.getByRole('button', { name: 'Add entry', exact: true }).click();
  await section.getByLabel('name entry 1', { exact: true }).fill('Live project');
  await section.getByLabel('technologies entry 1').fill('Python\nLaTeX');
  await section.getByLabel('Page break before').check();
  await section.getByRole('button', { name: 'Section up', exact: true }).click();
  const raw = page.getByTestId('studio-section').filter({ hasText: 'Legacy publications' });
  await raw.locator('summary').click();
  await raw.getByLabel('Include section', { exact: true }).uncheck();
  await page.getByText('All template sources (.tex / .cls / .sty)', { exact: true }).click();
  await page.getByLabel('Source file', { exact: true }).selectOption('resume.cls');
  await page.getByLabel('Template source', { exact: true }).fill('edited class');
  await page.getByRole('button', { name: 'CV Data Editor', exact: true }).click();
  await page.getByRole('button', { name: 'Template Studio', exact: true }).last().click();
  await page.getByText('All template sources (.tex / .cls / .sty)', { exact: true }).click();
  await page.getByLabel('Source file', { exact: true }).selectOption('resume.cls');
  await expect(page.getByLabel('Template source', { exact: true })).toHaveValue('edited class');
  await expect(page.getByRole('button', { name: 'Save new CV version', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Save template revision', exact: true }).click();
  await page.getByRole('button', { name: 'Save new CV version', exact: true }).click();
  await expect.poll(() => api.saved()?.cv.document?.sections[1].kind).toBe('entries');
  expect(api.saved()?.cv.document?.sections[2].enabled).toBe(false);
  expect(api.saved()?.cv.cv_template.revision).toBe('b'.repeat(64));
  expect(api.saved()?.cv.personal_statement).toBe('Unsaved Studio statement');
  expect(api.unexpected).toEqual([]);
});

test('Studio conflict is visible and preserves the unsaved draft', async ({ page }) => {
  const api = await setup(page);
  api.conflict();
  await page.getByRole('button', { name: 'Save template revision', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('reload');
  await expect(page.getByText('CV: unsaved · Template: unsaved')).toBeVisible();
  expect(api.saved()).toBeNull();
  expect(api.unexpected).toEqual([]);
});

test('unsaved preview survives tabs, rejects stale completion, decodes JSON blob errors and retains its last PDF', async ({ page }) => {
  await page.addInitScript(() => {
    const created: string[] = [], revoked: string[] = [];
    const create = URL.createObjectURL.bind(URL), revoke = URL.revokeObjectURL.bind(URL);
    URL.createObjectURL = blob => { const url = create(blob); created.push(url); return url; };
    URL.revokeObjectURL = url => { revoked.push(url); revoke(url); };
    Object.assign(window, { studioURLs: { created, revoked } });
  });
  const api = await setup(page);
  await page.getByRole('button', { name: 'Preview PDF', exact: true }).click();
  const frame = page.getByTitle('Studio PDF preview', { exact: true });
  await expect(frame).toHaveAttribute('src', /^blob:/);
  const firstURL = await frame.getAttribute('src');
  await page.locator('summary').filter({ hasText: /^Header LaTeX$/ }).click();
  await page.getByLabel('Header LaTeX', { exact: true }).fill('UNSAVED HEADER');
  await expect(page.getByRole('status')).toContainText('Preview outdated');
  const release = api.holdPreview();
  await page.getByRole('button', { name: 'Preview PDF', exact: true }).click();
  await expect.poll(() => api.previews.length).toBe(2);
  expect(api.previews[1].cv.document?.header_latex).toBe('UNSAVED HEADER');
  await page.getByLabel('Header LaTeX', { exact: true }).fill('NEWER HEADER');
  await page.getByRole('button', { name: 'CV Data Editor', exact: true }).click();
  release();
  await page.getByRole('button', { name: 'Template Studio', exact: true }).last().click();
  await expect(page.getByRole('button', { name: 'Preview PDF', exact: true })).toBeEnabled();
  await expect(frame).toHaveAttribute('src', firstURL!);
  await page.getByRole('button', { name: 'Preview PDF', exact: true }).click();
  await expect(frame).not.toHaveAttribute('src', firstURL!);
  const newURL = await frame.getAttribute('src');
  const urls = await page.evaluate(() => (window as unknown as { studioURLs: { created: string[]; revoked: string[] } }).studioURLs);
  expect(urls.created).toHaveLength(2);
  expect(urls.revoked).toEqual([firstURL]);
  api.failPreview();
  await page.getByRole('button', { name: 'Preview PDF', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('resume.cls:90');
  await expect(frame).toHaveAttribute('src', newURL!);
  expect(api.saved()).toBeNull();
  expect(api.unexpected).toEqual([]);
});

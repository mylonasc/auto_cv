import { defineConfig, devices } from '@playwright/test';

/** Opt-in visual E2E against a REAL backend on :8005 (Vite proxies /api there).
 *
 * Not part of `test:cv` (which mocks every API call). Start first, from the
 * repository root with an isolated data directory:
 *
 *   datastore=$(mktemp -d /tmp/opencode/auto_cv_visual_backend.XXXXXX)
 *   AUTO_CV_DATA_ROOT="$datastore" .venv/bin/python -m uvicorn \
 *     server_application.backend.main:app --host 127.0.0.1 --port 8005
 *
 * then from frontend/auto-cv-customizer: `npm run test:visual`.
 * Requires local XeLaTeX and poppler-utils on the BACKEND host. No LLM calls
 * are made; only synthetic CVs are compiled. PDFs are attached to the report
 * for human review.
 */
export default defineConfig({
  testDir: './tests',
  testMatch: ['render-visual.spec.ts'],
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 180000,
  reporter: 'list',
  outputDir: 'test-results/visual',
  use: {
    baseURL: 'http://127.0.0.1:5189',
    serviceWorkers: 'block',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5189 --strictPort',
    url: 'http://127.0.0.1:5189',
    reuseExistingServer: false,
  },
});

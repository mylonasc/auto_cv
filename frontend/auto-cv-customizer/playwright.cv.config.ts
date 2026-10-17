import { defineConfig, devices } from '@playwright/test';

/** Isolated UI contract checks: all API traffic is mocked, never proxied to user data. */
export default defineConfig({
  testDir: './tests',
  testMatch: ['cv-editing.spec.ts', 'workflow.spec.ts'],
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: 'list',
  outputDir: 'test-results/cv-schema',
  use: {
    baseURL: 'http://127.0.0.1:5187',
    serviceWorkers: 'block',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5187 --strictPort',
    url: 'http://127.0.0.1:5187',
    reuseExistingServer: false,
  },
});

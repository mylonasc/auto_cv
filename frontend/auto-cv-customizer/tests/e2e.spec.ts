import { test, expect } from '@playwright/test';

test.describe('CV Customizer E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Wait for the app to be stable
    await expect(page.locator('.app-title')).toBeVisible();
  });

  test('should load the home page and show job input grid', async ({ page }) => {
    await expect(page.getByRole('heading', { name: '1. Job Description' })).toBeVisible();
    await expect(page.getByRole('heading', { name: '2. Review CV Experience' })).toBeVisible();
    await expect(page.locator('#jobTitle')).toBeVisible();
    await expect(page.locator('#companyName')).toBeVisible();
    await expect(page.locator('#jobText')).toBeVisible();
  });

  test('should load example job description', async ({ page }) => {
    await page.getByRole('button', { name: 'Example' }).click();
    
    await expect(page.locator('#jobTitle')).toHaveValue('Senior ML Engineer Example');
    await expect(page.locator('#companyName')).toHaveValue('TechCorp AI');
    await expect(page.locator('#jobText')).not.toBeEmpty();
  });

  test('should save a job and show it in the sidebar', async ({ page }) => {
    const jobTitle = 'Test Job Title ' + Date.now();
    const company = 'Test Company';
    
    await page.fill('#jobTitle', jobTitle);
    await page.fill('#companyName', company);
    await page.fill('#jobText', 'This is a test job description for Playwright E2E.');
    
    await page.getByRole('button', { name: 'Save Job' }).click();
    
    // Ensure sidebar is expanded to check visibility
    const sidebar = page.locator('aside.sidebar');
    const isCollapsed = await sidebar.evaluate(el => el.classList.contains('collapsed'));
    if (isCollapsed) {
      await page.getByRole('button', { name: 'Toggle sidebar' }).click();
    }

    const sidebarJob = page.locator('.job-list .job-item').filter({ hasText: jobTitle });
    await expect(sidebarJob).toBeVisible({ timeout: 10000 });
    await expect(sidebarJob.locator('.job-company')).toHaveText(company);
  });

  test('should navigate to processing tab after saving a job', async ({ page }) => {
    await page.getByRole('button', { name: 'Example' }).click();
    await page.getByRole('button', { name: 'Save Job' }).click();
    
    // Wait for the start banner to appear
    const startBtn = page.getByRole('button', { name: 'Start AI Analysis →' });
    await expect(startBtn).toBeVisible({ timeout: 10000 });
    await startBtn.click();
    
    // Verify we are on processing tab
    await expect(page.locator('.sidebar-nav li.active')).toContainText('Processing');
    await expect(page.getByRole('heading', { name: 'CV Processing', exact: true })).toBeVisible();
  });

  test('should toggle sidebar', async ({ page }) => {
    const sidebar = page.locator('aside.sidebar');
    
    // Initial state: not collapsed
    await expect(sidebar).not.toHaveClass(/collapsed/);
    
    // Click toggle in header to collapse
    await page.getByRole('button', { name: 'Toggle sidebar' }).click();
    await expect(sidebar).toHaveClass(/collapsed/);
    
    // Click toggle in header to expand
    await page.getByRole('button', { name: 'Toggle sidebar' }).click();
    await expect(sidebar).not.toHaveClass(/collapsed/);
  });

  test('should show configuration panel', async ({ page }) => {
    // Ensure sidebar is expanded
    const sidebar = page.locator('aside.sidebar');
    const isCollapsed = await sidebar.evaluate(el => el.classList.contains('collapsed'));
    if (isCollapsed) {
      await page.getByRole('button', { name: 'Toggle sidebar' }).click();
    }

    await page.getByRole('button', { name: 'Settings' }).click();
    await expect(page.getByRole('heading', { name: 'Backend Configuration' })).toBeVisible();
    
    // Close it
    await page.locator('.modal-close').click();
    await expect(page.getByRole('heading', { name: 'Backend Configuration' })).not.toBeVisible();
  });
});

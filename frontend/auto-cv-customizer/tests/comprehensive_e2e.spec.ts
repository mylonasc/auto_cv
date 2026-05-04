import { test, expect } from '@playwright/test';

test.describe('CV Customizer Comprehensive E2E', () => {
  test('should process a CV end-to-end', async ({ page }) => {
    // 1. Go to home page
    await page.goto('/');
    await expect(page.locator('.app-title')).toBeVisible();

    // 2. Load example job
    await page.getByRole('button', { name: 'Example' }).click();
    
    // 3. Save job
    await page.getByRole('button', { name: 'Save Job' }).click();
    
    // 4. Navigate to Processing tab
    const navigateBtn = page.getByRole('button', { name: 'Start AI Analysis →' });
    await expect(navigateBtn).toBeVisible({ timeout: 10000 });
    await navigateBtn.click();

    // 5. Start actual processing
    const startBtn = page.getByRole('button', { name: 'Start Processing', exact: true });
    await expect(startBtn).toBeVisible();
    await startBtn.click();

    // 6. Wait for processing to complete.
    // We expect it to eventually switch to the Results tab automatically.
    test.setTimeout(200000); // 3.3 minutes
    
    // Instead of waiting for the badge (which might disappear quickly when tab switches),
    // wait for the Results heading which indicates success and tab switch.
    await expect(page.getByRole('heading', { name: 'CV Analysis Results' })).toBeVisible({ timeout: 180000 });
    
    // 7. Check if results are displayed
    const sections = page.locator('.section-card');
    await expect(sections.first()).toBeVisible();
    
    // 8. Test Export Dialog
    // Wait a bit for state to settle
    await page.waitForTimeout(2000);
    await page.getByRole('button', { name: '📦 Export CV' }).click();
    await expect(page.getByRole('heading', { name: 'Export & Download' })).toBeVisible();
    
    // Check for the Download button in the artifact card
    const downloadBtn = page.getByRole('button', { name: 'Download' }).first();
    await expect(downloadBtn).toBeVisible();
  });
});

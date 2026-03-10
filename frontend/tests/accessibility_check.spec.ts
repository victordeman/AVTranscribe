import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Accessibility Scan', () => {
  test('should not have any detectable WCAG violations on the home page', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await expect(page.locator('h1')).toHaveText('AVTranscribe');
    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();
    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('should have specific ARIA attributes for accessibility', async ({ page }) => {
    await page.goto('http://localhost:5173');
    const uploadTitle = page.locator('#upload-form-title');
    await expect(uploadTitle).toBeVisible();
    await expect(uploadTitle).toHaveText('Upload Media');
    const form = page.locator('form');
    await expect(form).toHaveAttribute('aria-labelledby', 'upload-form-title');
    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toHaveAttribute('aria-describedby', 'file-input-help');
    const submitButton = page.locator('button[type="submit"]');
    const icon = submitButton.locator('svg');
    await expect(icon).toHaveAttribute('aria-hidden', 'true');
  });
});

import { test, expect } from '@playwright/test';
for (const locale of ['', 'zh-CN/']) {
  test(`mechanisms retain their scope and reference links ${locale}`, async ({ page }) => {
    await page.goto(locale ? 'index.zh-CN/' : './');
    await expect(page.locator('[data-mechanism]')).toHaveCount(6);
    await expect(page.locator('.framework-track li')).toHaveCount(4);
    await expect(page.locator('.mechanism-scope')).toHaveCount(6);
    await expect(page.locator('.editorial-actions a')).toHaveCount(1);
    for (const href of await page.locator('.mechanism-links a, .framework-comparison > a').evaluateAll(nodes => nodes.map(n => (n as HTMLAnchorElement).href))) {
      expect((await page.request.get(href)).ok()).toBeTruthy();
    }
    await page.locator('.mechanism-advanced summary').click();
    await expect(page.locator('.mechanism-advanced li')).toHaveCount(3);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  });
}

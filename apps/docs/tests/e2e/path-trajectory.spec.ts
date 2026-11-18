import { test, expect } from "@playwright/test";
for (const locale of ["", "zh-CN/"]) {
  test(`recorded trajectories preserve the shared scale and selected account ${locale}`, async ({ page }) => {
    await page.goto(`learn/${locale}paths/`);
    const deep=page.locator('.path-lane[data-preset="deep"]');
    const plot=deep.locator('.path-plot[data-trajectory="true"]');
    await expect(plot).toBeVisible();
    const points=(await plot.locator('.path-record-line').getAttribute('points'))!.split(' ').map(p=>p.split(',').map(Number));
    expect(points.map(p=>p[1])).toEqual([80,50,20]);
    expect(points[1][0]).toBeCloseTo(12+76*4/7,8);
    await expect(plot.locator('.path-record-quantity strong')).toHaveText(['0','500','1,000']);
    await plot.locator('button').nth(1).click();
    await expect(deep).toHaveAttribute('data-active','true');
    await expect(deep.locator('.path-summary [data-field="quantity"] strong')).toHaveAttribute('data-value','500');
    await expect(deep.locator('.path-summary [data-field="cash"] strong')).toHaveAttribute('data-value','5000');
    expect((await plot.locator('.path-observed-line').getAttribute('points'))!.split(' ')).toHaveLength(2);
    const width=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,viewport:innerWidth}));
    expect(width.scroll).toBeLessThanOrEqual(width.viewport+1);
  });
}

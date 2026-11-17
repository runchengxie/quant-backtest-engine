import {test,expect} from '@playwright/test';
for(const locale of ['en','zh-CN']) {
 test(`${locale} direct reference search and navigation`,async({page})=>{
  await page.goto(locale==='en'?'contracts/':'contracts.zh-CN/');
  await expect(page.locator('article.reference-document')).toBeVisible();
  await page.locator('#reference-query').fill(locale==='en'?'execution':'执行');
  await expect(page.locator('#reference-results a').first()).toBeVisible();
  const urls=await page.locator('#reference-results a').evaluateAll(links=>links.map(a=>a.getAttribute('href')));
  expect(urls.length).toBeGreaterThan(0);
  for(const href of urls) expect(href?.includes('.zh-CN')).toBe(locale==='zh-CN');
 });
 test(`${locale} reference works without JavaScript`,async({browser,baseURL})=>{
  const context=await browser.newContext({javaScriptEnabled:false,baseURL});
  const page=await context.newPage();
  await page.goto(locale==='en'?'backtesting-explained/':'backtesting-explained.zh-CN/');
  await expect(page.locator('.method-scene')).toHaveCount(8);
  await expect(page.locator('article.reference-document')).toContainText('10019.78');
  await expect(page.locator('.reference-navigation')).toBeVisible();
  // The explicit language link must remain available without scripts.
  await context.close();
 });
}

import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const inventory = JSON.parse(
  readFileSync(
    new URL("../../../docs/site/legacy-route-anchors.json", import.meta.url),
    "utf8",
  ),
);
test("every legacy route and observed fragment remains in actual served HTML", async ({
  request,
}) => {
  for (const [path, page] of Object.entries(inventory.html) as [
    string,
    { ids: string[] },
  ][]) {
    const response = await request.get(path);
    expect(response.status(), path).toBe(200);
    const text = await response.text();
    for (const id of page.ids)
      expect(text, path + "#" + id).toContain('id="' + id + '"');
  }
});
test("Chinese home and tutorial numeric anchors, direct HTML and encoded fragment navigation", async ({
  page,
}) => {
  for (const url of [
    "index.zh-CN/index.html#_4",
    "backtesting-explained.zh-CN/index.html#8",
    "backtesting-explained.zh-CN/#%31",
  ]) {
    await page.goto(url);
    const id = decodeURIComponent(new URL(page.url()).hash.slice(1));
    await expect(page.locator(`[id="${id}"]`)).toBeVisible();
  }
});

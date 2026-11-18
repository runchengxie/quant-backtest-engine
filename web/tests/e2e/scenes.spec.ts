import { test, expect } from "@playwright/test";
// Exact-record assertions use manual mode; automatic playback has dedicated coverage.
test.use({ reducedMotion: "reduce" });
const presets = {
  flow: ["roundtrip"],
  book: ["depth"],
  impact: ["small", "large", "nondecaying", "close"],
  cost: ["once"],
  lots: ["no-minimum", "minimum", "grid"],
  paths: ["thin", "deep", "market-up", "feedback"],
  selection: ["null-search"],
  risk: [
    "recovery",
    "shared",
    "residual",
    "actions",
    "risk-full",
    "risk-missing",
  ],
};
for (const locale of ["en", "zh-CN"])
  for (const [scene, ids] of Object.entries(presets))
    test(`${locale} ${scene}: exact presets, synchronized views, keyboard and static coverage`, async ({
      page,
    }) => {
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(String(e)));
      page.on("response", (r) => {
        if (r.status() >= 400) errors.push(r.status() + " " + r.url());
      });
      await page.goto(`lab/${locale === "en" ? "" : "zh-CN/"}${scene}/`);
      await expect(page.locator("[data-ready=true]")).toBeVisible();
      await expect(page.locator("[data-static-preset]")).toHaveCount(
        ids.length,
      );
      const select = page.locator(".learning-controls select").first();
      await expect(select.locator("option")).toHaveCount(ids.length);
      for (const id of ids) {
        await select.selectOption(id);
        await expect(page.locator(".learning-workbench")).toHaveAttribute(
          "data-current-event",
          `${scene}.${id}.0`,
        );
        await page.locator("[data-action=next]").click();
        const event = await page
          .locator(".learning-workbench")
          .getAttribute("data-current-event");
        await expect(page.locator("[data-view=causal]")).toHaveAttribute(
          "data-event",
          event!,
        );
        await expect(page.locator("[data-view=chart]")).toHaveAttribute(
          "data-event",
          event!,
        );
        await page.locator("[data-action=reset]").click();
        await expect(page.locator(".learning-workbench")).toHaveAttribute(
          "data-current-event",
          `${scene}.${id}.0`,
        );
        if (
          (await page.locator(".teaching-evidence").getAttribute("open")) ===
          null
        )
          await page.locator(".teaching-evidence > summary").click();
        const timeline = page.locator('section[tabindex="0"]');
        await timeline.focus();
        await page.keyboard.press("ArrowRight");
        await expect(page.locator(".learning-workbench")).toHaveAttribute(
          "data-current-event",
          `${scene}.${id}.1`,
        );
      }
      expect(errors).toEqual([]);
    });
test("comparison uses independently recorded account", async ({ page }) => {
  await page.goto("lab/paths/");
  await expect(page.locator("[data-ready=true]")).toBeVisible();
  await page.locator(".teaching-evidence > summary").click();
  await page
    .getByRole("checkbox", { name: "Same market · 50% participation" })
    .check();
  await page.locator("[data-action=next]").click();
  await page.locator("[data-action=next]").click();
  await expect(
    page.locator("[data-view=comparison] [data-preset=deep]"),
  ).toHaveAttribute("data-event", "paths.deep.2");
  await expect(page.locator("[data-view=comparison]")).toContainText("0");
});

import { test, expect } from "@playwright/test";
test.use({ reducedMotion: "reduce" });
for (const locale of ["", "zh-CN/"]) {
  test(`diagram hierarchy matches the mechanism index ${locale}`, async ({
    page,
  }) => {
    for (const scene of [
      "flow",
      "book",
      "cost",
      "impact",
      "lots",
      "paths",
      "selection",
      "risk",
    ]) {
      await page.goto(`learn/${locale}${scene}/`);
      await expect(page.locator("[data-ready=true]")).toBeVisible();
      const breadcrumb = page.locator(
        ".editorial-lesson-heading .learning-kicker",
      );
      await expect(breadcrumb).toHaveText(
        locale ? "机制总览" : "Mechanism overview",
      );
      await expect(page.locator(".lesson-category")).toHaveText(
        locale
          ? scene === "flow"
            ? "账户核对"
            : ["selection", "risk"].includes(scene)
              ? "进阶验证"
              : "交互演示"
          : scene === "flow"
            ? "Account reconciliation"
            : ["selection", "risk"].includes(scene)
              ? "Further validation"
              : "Interactive demonstration",
      );
      await expect(page.locator(".diagram-meta time")).not.toBeEmpty();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBeTruthy();
    }
  });
  test(`path branches preserve each aligned account ${locale}`, async ({
    page,
  }) => {
    await page.goto(`learn/${locale}paths/`);
    await expect(page.locator("[data-ready=true]")).toBeVisible();
    await page
      .locator("[data-preset=feedback] .path-events button")
      .nth(1)
      .click();
    await expect(page.locator(".learning-workbench")).toHaveAttribute(
      "data-current-event",
      "paths.feedback.1",
    );
    for (const [id, quantity] of [
      ["thin", "100"],
      ["deep", "500"],
      ["feedback", "100"],
      ["market-up", "100"],
    ]) {
      await expect(
        page.locator(`.path-lane[data-preset="${id}"]`),
      ).toHaveAttribute("data-aligned-record", `paths.${id}.1`);
      await expect(
        page.locator(
          `.path-lane[data-preset="${id}"] [data-field=quantity] strong`,
        ),
      ).toHaveAttribute("data-value", quantity);
    }
    await page
      .locator("[data-preset=market-up] .path-events button")
      .last()
      .click();
    await expect(page.locator(".learning-workbench")).toHaveAttribute(
      "data-current-event",
      "paths.market-up.2",
    );
    await expect(
      page.locator(
        ".path-lane[data-preset=market-up] [data-field=cash] strong",
      ),
    ).toHaveAttribute("data-value", "7950");
  });
}

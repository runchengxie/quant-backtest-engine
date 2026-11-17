import { test, expect } from "@playwright/test";
for (const locale of ["", "zh-CN/"]) {
  test(`teaching book event selection keeps exact state ${locale}`, async ({
    page,
  }) => {
    await page.goto(`lab/${locale}book/`);
    await expect(page.locator("[data-ready=true]")).toBeVisible();
    const report = page.locator(".teaching-ladder button").last();
    await report.focus();
    await page.keyboard.press("Enter");
    await expect(page.locator(".teaching-scenes")).toHaveAttribute(
      "data-event",
      "book.depth.3",
    );
    await expect(
      page.locator(".teaching-scenes [data-field=remaining] strong"),
    ).toHaveText("5");
    await expect(
      page.locator(".teaching-scenes [data-field=reported] strong"),
    ).toHaveText("15");
    await expect(
      page.locator(".teaching-ladder [data-active=true]"),
    ).toHaveCount(1);
    await expect(page.locator(".teaching-map li")).toHaveCount(6);
  });
  test(`teaching account lanes retain independent unknowns ${locale}`, async ({
    page,
  }) => {
    await page.goto(`lab/${locale}paths/`);
    await expect(page.locator("[data-ready=true]")).toBeVisible();
    await expect(page.locator(".teaching-paths article")).toHaveCount(4);
    for (const button of await page
      .locator(".teaching-paths [data-preset=deep] button")
      .all())
      await expect(button).toBeDisabled();
    await page
      .locator(".teaching-paths [data-preset=thin] button")
      .last()
      .click();
    await expect(page.locator(".teaching-scenes")).toHaveAttribute(
      "data-event",
      "paths.thin.2",
    );
    await expect(
      page.locator(".teaching-paths [data-preset=deep] [data-active=true]"),
    ).toHaveCount(0);
  });
}
const primary = {
  flow: ".teaching-transfer",
  book: ".teaching-ladder",
  impact: ".teaching-curves",
  cost: ".teaching-bars",
  lots: ".teaching-landscape",
  paths: ".teaching-paths",
  selection: ".teaching-trials",
  risk: ".teaching-bars",
};
for (const [scene, selector] of Object.entries(primary))
  test(`teaching ${scene} opens with one custom visual and folded evidence`, async ({
    page,
  }) => {
    await page.goto(`lab/${scene}/`);
    await expect(page.locator("[data-ready=true]")).toBeVisible();
    await expect(page.locator(".teaching-scenes " + selector)).toBeVisible();
    await expect(page.locator(".teaching-scenes > section")).toHaveCount(1);
    await expect(page.locator(".teaching-evidence")).not.toHaveAttribute(
      "open",
      "",
    );
    await expect(page.locator("[data-view=chart]")).not.toBeVisible();
  });
test("prepared opportunity cases change signed owner outputs without changing replay event", async ({
  page,
}) => {
  await page.goto("lab/cost/");
  await expect(page.locator("[data-ready=true]")).toBeVisible();
  const before = await page
    .locator(".learning-workbench")
    .getAttribute("data-current-event");
  await page.locator(".teaching-opportunity > summary").click();
  const example = page.locator(".teaching-opportunity-example");
  for (const [id, expected] of [
    ["down", "-200.0"],
    ["flat", "0.0"],
    ["up", "+200.0"],
  ]) {
    await example.locator("select").selectOption(id);
    await expect(example).toHaveAttribute("data-example-id", id);
    await expect(
      example.locator('[data-example-field="opportunity.unfilled"] strong'),
    ).toHaveText(expected);
    await expect(
      example.locator('[data-example-field="opportunity.executed"] strong'),
    ).toHaveText("+15.0");
    await expect(page.locator(".learning-workbench")).toHaveAttribute(
      "data-current-event",
      before!,
    );
  }
});

test("impact SVG titles survive server rendering and hydration", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("learn/impact/");
  await expect(page.locator("[data-ready=true]")).toBeVisible();
  await expect(page.locator(".teaching-curves circle title").first()).toHaveText("Transient displacement: 0.2");
  expect(errors).toEqual([]);
});

test("first theme click reverses the system dark preference", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("learn/flow/");
  await page.locator("#product-theme").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

import { test, expect } from "@playwright/test";
for (const locale of ["en", "zh-CN"])
  test(`${locale} no JavaScript retains every preset and exact tables`, async ({
    browser,
    baseURL,
  }) => {
    const context = await browser.newContext({
      javaScriptEnabled: false,
      baseURL,
    });
    const page = await context.newPage();
    await page.goto(`lab/${locale === "en" ? "" : "zh-CN/"}risk/`);
    await expect(page.locator("[data-static-preset]")).toHaveCount(6);
    await expect(page.locator("[data-static-preset=actions]")).toContainText(
      "10400",
    );
    await expect(
      page.locator(".learning-controls select").first(),
    ).toBeDisabled();
    await page
      .locator("[data-static-preset=shared] details")
      .nth(1)
      .locator("summary")
      .click();
    await expect(
      page.locator("[data-static-preset=shared] details").nth(1),
    ).toHaveAttribute("open", "");
    await context.close();
  });
test("320px, both themes, reduced motion and stored explicit locale", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("lab/impact/");
  await expect(page.locator("[data-ready=true]")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Play", exact: true }),
  ).toBeDisabled();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("button", { name: "Toggle color theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("link", { name: "简体中文", exact: true }).click();
  await expect(page).toHaveURL(/lab\/zh-CN\/impact\/$/);
  expect(
    await page.evaluate(() => localStorage.getItem("engine.site.locale.v1")),
  ).toBe("zh-CN");
  await page.goBack();
  await expect(page.locator("[data-ready=true]")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Play", exact: true }),
  ).toBeDisabled();
});
test("blocked storage cannot break hydration or explicit deep links", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "localStorage", {
      get() {
        throw Error("blocked");
      },
    });
  });
  await page.goto("lab/zh-CN/book/#product-book");
  await expect(page.locator("[data-ready=true]")).toBeVisible();
  expect(new URL(page.url()).hash).toBe("#product-book");
  await page.locator(".learning-controls button").nth(1).click();
  await expect(page.locator(".learning-workbench")).toHaveAttribute(
    "data-current-event",
    "book.depth.1",
  );
});
test("bad hydration payload disables replay and preserves static evidence", async ({
  page,
}) => {
  await page.route("**/lab/flow/", async (route) => {
    const response = await route.fetch();
    let text = await response.text();
    text = text.replaceAll(
      "engine-learning-trace.v1",
      "invalid-learning-trace",
    );
    await route.fulfill({ response, body: text });
  });
  await page.goto("lab/flow/");
  await expect(page.getByRole("alert")).toContainText(
    "Replay data validation failed",
  );
  await expect(page.locator("[data-static-preset=roundtrip]")).toContainText(
    "10019.78",
  );
});

test("playback pauses on hidden tab, does not resume, and navigation cleans timers", async ({
  page,
}) => {
  await page.goto("lab/impact/");
  await expect(page.locator("[data-ready=true]")).toBeVisible();
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await page.evaluate(() => {
    Object.defineProperty(document, "hidden", {
      configurable: true,
      get: () => true,
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect(
    page.getByRole("button", { name: "Play", exact: true }),
  ).toBeVisible();
  const id = await page
    .locator(".learning-workbench")
    .getAttribute("data-current-event");
  await page.waitForTimeout(1100);
  await expect(page.locator(".learning-workbench")).toHaveAttribute(
    "data-current-event",
    id!,
  );
  await page.evaluate(() => {
    Object.defineProperty(document, "hidden", {
      configurable: true,
      get: () => false,
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await page.waitForTimeout(1100);
  await expect(page.locator(".learning-workbench")).toHaveAttribute(
    "data-current-event",
    id!,
  );
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await page
    .getByRole("link", { name: "Read the explanation", exact: true })
    .click();
  await page.goBack();
  await expect(
    page.getByRole("button", { name: "Play", exact: true }),
  ).toBeVisible();
});

test("explicit language preference crosses the legacy renderer without deep-link redirect", async ({
  page,
}) => {
  await page.goto("lab/flow/");
  await page.getByRole("link", { name: "简体中文", exact: true }).click();
  await page.goto("backtesting-explained.zh-CN/#1");
  expect(new URL(page.url()).hash).toBe("#1");
  const english = page.locator("a[hreflang=en]");
  await expect(english).toHaveCount(1);
  await page.getByRole("button", { name: "选择当前语言", exact: true }).click();
  await english.click();
  await expect(page).toHaveURL(/backtesting-explained\/#/);
  expect(
    await page.evaluate(() => localStorage.getItem("engine.site.locale.v1")),
  ).toBe("en");
});

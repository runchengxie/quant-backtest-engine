import { test, expect } from "@playwright/test";
for (const locale of ["", "zh-CN/"]) {
  test(`six distinct entries and source-bound account feedback ${locale}`, async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto(locale ? "index.zh-CN/" : "");
    const links = page.locator(
      "[data-mechanism] .mechanism-links a:first-child",
    );
    expect(await links.count()).toBe(6);
    const urls = await links.evaluateAll((xs) =>
      xs.map((x) => (x as HTMLAnchorElement).href),
    );
    expect(new Set(urls).size).toBe(6);
    await page.goto(`learn/${locale}feedback/`);
    await expect(
      page.locator(".learning-workbench[data-ready=true]"),
    ).toBeVisible();
    await expect(page.locator("[data-feedback-record]")).toHaveAttribute(
      "data-feedback-record",
      "paths.feedback.0",
    );
    await page.locator("[data-action=next]").click();
    await expect(page.locator("[data-target]")).toHaveAttribute(
      "data-target",
      "0.1",
    );
    await expect(
      page.locator('.feedback-account [data-value="100"]'),
    ).toBeVisible();
    await expect(
      page.locator('.feedback-account [data-value="9000"]'),
    ).toBeVisible();
    await page.locator("[data-action=next]").click();
    await expect(
      page.locator('.feedback-fixed [data-value="200"]'),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
  });
  test(`queue arrival and cancel races use owner records ${locale}`, async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto(`learn/${locale}book/`);
    const root = page.locator("[data-step-player=queue]");
    await expect(root).toHaveAttribute("data-step-ready", "true");
    await expect(root.locator("[data-step-action=play]")).toBeDisabled();
    for (let i = 0; i < 3; i++)
      await root.locator("[data-step-action=next]").click();
    await expect(root.locator("[data-fill-buy=own]")).toHaveAttribute(
      "data-fill-quantity",
      "2",
    );
    await page.locator(".event-preset select").selectOption("late");
    for (let i = 0; i < 3; i++)
      await root.locator("[data-step-action=next]").click();
    await expect(root.locator("[data-order=own]")).toBeVisible();
    await expect(root.locator("[data-fill-buy=own]")).toHaveCount(0);
    await page.locator(".event-preset select").selectOption("cancel-late");
    for (let i = 0; i < 2; i++)
      await root.locator("[data-step-action=next]").click();
    await expect(root.locator("[data-queue-event]")).toHaveAttribute(
      "data-queue-event",
      "cancel",
    );
    await expect(root.locator("[data-clock=arrival]")).toHaveText("250 ns");
    await expect(root.locator("[data-order=own]")).toHaveCount(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
  });
}
test("home flow loops and pauses with manual transport", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.clock.install();
  await page.goto("");
  const root = page.locator("[data-step-player=framework]");
  await root.scrollIntoViewIfNeeded();
  await expect(root).toHaveAttribute("data-playing", "true");
  for (let i = 1; i <= 4; i++) {
    await page.clock.runFor(2700);
    await expect(root).toHaveAttribute("data-step", String(i));
  }
  await page.clock.runFor(3500);
  await expect(root).toHaveAttribute("data-step", "0");
  await root.locator("[data-step-action=next]").click();
  await expect(root).toHaveAttribute("data-playing", "false");
  await page.clock.runFor(6000);
  await expect(root).toHaveAttribute("data-step", "1");
  await root.locator("[data-step-action=reset]").click();
  await expect(root).toHaveAttribute("data-step", "0");
});

test("feedback automatically advances source events and pauses offscreen", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.clock.install();
  await page.goto("learn/feedback/");
  const root = page.locator(".learning-workbench");
  await page.locator("[data-motion-stage=feedback]").scrollIntoViewIfNeeded();
  await expect(root).toHaveAttribute("data-playing", "true");
  await page.clock.runFor(2500);
  await expect(page.locator("[data-feedback-record]")).toHaveAttribute(
    "data-feedback-record",
    "paths.feedback.1",
  );
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect(root).toHaveAttribute("data-playing", "false");
});

test("all queue case tables remain readable without JavaScript", async ({
  browser,
}) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto("learn/zh-CN/book/");
  await page.locator(".queue-demo details summary").click();
  await expect(page.locator("[data-queue-table]")).toHaveCount(4);
  await expect(page.locator("[data-queue-table=timely]")).toContainText(
    "own 2 @ 100",
  );
  await expect(page.locator("[data-queue-table=cancel-late]")).toContainText(
    "own 3 @ 100",
  );
  await context.close();
});

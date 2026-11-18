import {test,expect} from "@playwright/test";

test("visible chart automatically loops, then manual transport pauses and seeks exact events",async({page})=>{
  await page.emulateMedia({reducedMotion:"no-preference"});
  await page.clock.install();
  await page.goto("learn/flow/");
  await expect(page.locator("[data-ready=true]")).toBeVisible();
  await page.locator("[data-motion-stage]").scrollIntoViewIfNeeded();
  await expect(page.locator(".learning-workbench")).toHaveAttribute("data-playing","true");
  await page.clock.runFor(9200);
  await expect(page.locator(".learning-workbench")).toHaveAttribute("data-playing","true");
  await page.locator("[data-action=play]").scrollIntoViewIfNeeded();
  // On a narrow screen scrolling back to controls can already pause the offscreen chart.
  if (await page.locator("[data-action=play]").getAttribute("aria-pressed") === "true")
    await page.locator("[data-action=play]").click();
  await expect(page.locator(".learning-workbench")).toHaveAttribute("data-playing","false");
  await page.locator("[data-action=reset]").click();
  await expect(page.locator(".learning-workbench")).toHaveAttribute("data-current-event","flow.roundtrip.0");
  await page.locator("[data-action=next]").click();
  await expect(page.locator(".learning-workbench")).toHaveAttribute("data-current-event","flow.roundtrip.1");
  await page.locator("[data-action=previous]").click();
  await expect(page.locator(".learning-workbench")).toHaveAttribute("data-current-event","flow.roundtrip.0");
  await page.locator(".replay-scrubber input").focus();
  await page.keyboard.press("End");
  await expect(page.locator(".learning-workbench")).toHaveAttribute("data-current-event","flow.roundtrip.2");
  await page.clock.runFor(10000);
  await expect(page.locator(".learning-workbench")).toHaveAttribute("data-current-event","flow.roundtrip.2");
  await page.locator("[data-action=play]").click();
  await page.clock.runFor(3400);
  await expect(page.locator(".learning-workbench")).toHaveAttribute("data-current-event","flow.roundtrip.0");
  await page.locator(".learning-controls select").nth(1).selectOption("2");
  await expect(page.locator(".learning-workbench")).toHaveAttribute("data-playing","false");
});

test("scrolling away pauses playback and returning keeps the selected record",async({page})=>{
  await page.emulateMedia({reducedMotion:"no-preference"});
  await page.goto("learn/book/");
  await expect(page.locator("[data-ready=true]")).toBeVisible();
  await page.locator("[data-motion-stage]").scrollIntoViewIfNeeded();
  await expect(page.locator(".learning-workbench")).toHaveAttribute("data-playing","true");
  await page.locator("footer").scrollIntoViewIfNeeded();
  await expect(page.locator(".learning-workbench")).toHaveAttribute("data-playing","false");
  const current=await page.locator(".learning-workbench").getAttribute("data-current-event");
  await page.locator("[data-motion-stage]").scrollIntoViewIfNeeded();
  await page.waitForTimeout(2700);
  await expect(page.locator(".learning-workbench")).toHaveAttribute("data-playing","false");
  await expect(page.locator(".learning-workbench")).toHaveAttribute("data-current-event",current!);
});

test("reduced motion leaves automatic loops and transitions off while step buttons work",async({page})=>{
  await page.emulateMedia({reducedMotion:"reduce"});
  await page.goto("learn/zh-CN/book/");
  await expect(page.locator("[data-ready=true]")).toBeVisible();
  await page.locator("[data-motion-stage]").scrollIntoViewIfNeeded();
  await expect(page.locator(".learning-workbench")).toHaveAttribute("data-playing","false");
  await expect(page.locator(".learning-workbench")).toHaveAttribute("data-motion-allowed","false");
  await expect(page.locator("[data-action=play]")).toBeDisabled();
  await page.locator("[data-action=next]").click();
  await expect(page.locator(".motion-caption")).toContainText("5");
  await expect(page.locator(".motion-shares [data-filled=true]")).toHaveCount(5);
  expect(await page.locator(".motion-bar").first().evaluate(node=>getComputedStyle(node).transitionDuration)).toBe("0s");
});

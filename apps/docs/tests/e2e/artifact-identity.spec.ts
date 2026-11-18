import { test, expect } from "@playwright/test";
import { createHash } from "node:crypto";
test("all raw served trace bytes and embedded identity match manifest", async ({
  request,
  page,
}) => {
  const response = await request.get("assets/learning/manifest.json");
  const raw = await response.body();
  const manifest = JSON.parse(raw.toString());
  for (const entry of [
    manifest.fixture,
    manifest.sources,
    manifest.preset_grid,
    ...Object.values(manifest.catalogs),
    ...manifest.traces,
  ] as { url: string; sha256: string }[]) {
    const result = await request.get(entry.url);
    expect(result.status()).toBe(200);
    expect(
      createHash("sha256")
        .update(await result.body())
        .digest("hex"),
    ).toBe(entry.sha256);
  }
  await page.goto("lab/flow/");
  await expect(page.locator(".learning-workbench")).toHaveAttribute(
    "data-manifest",
    createHash("sha256").update(raw).digest("hex"),
  );
  const trace = await (
    await request.get("assets/learning/traces/flow/roundtrip.json")
  ).json();
  await expect(page.locator("[data-static-preset=roundtrip]")).toContainText(
    trace.events[0].clock.value,
  );
});

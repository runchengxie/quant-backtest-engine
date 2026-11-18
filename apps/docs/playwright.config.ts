import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30000,
  workers: 2,
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 900 } } },
    { name: "mobile", use: { viewport: { width: 320, height: 740 } } },
  ],
  reporter: [
    ["list"],
    ["json", { outputFile: process.env.BROWSER_OUTPUT_DIR + "/results.json" }],
  ],
  outputDir: process.env.BROWSER_OUTPUT_DIR + "/test-results",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL,
    headless: true,
    launchOptions: {
      ...(process.env.CHROME_EXECUTABLE
        ? { executablePath: process.env.CHROME_EXECUTABLE }
        : {}),
      // Playwright keeps profiles in task data; Chrome needs short Unix socket paths.
      env: {
        ...process.env,
        TMPDIR: process.env.CHROME_SOCKET_TMPDIR || "/tmp",
      },
    },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});

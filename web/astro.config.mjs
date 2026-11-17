import { defineConfig } from "astro/config";
import react from "@astrojs/react";
import { readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../", import.meta.url));
execFileSync(process.execPath, [root + "project_tools/frontend_security.cjs", "verify", root + "web"], { stdio: "pipe" });
const input = process.env.SITE_INPUT_DIR;
const out = process.env.ASTRO_OUT_DIR;
export default defineConfig({
  site: "https://runchengxie.github.io",
  base: "/quant-backtest-engine/",
  output: "static",
  publicDir: input ? input + "/public" : "./public",
  trailingSlash: "always",
  outDir: out || fileURLToPath(new URL("./dist/", import.meta.url)),
  cacheDir:
    process.env.ASTRO_CACHE_DIR ||
    fileURLToPath(new URL("./.astro/", import.meta.url)),
  vite: { cacheDir: process.env.ASTRO_CACHE_DIR ? process.env.ASTRO_CACHE_DIR + "/vite" : "./.astro/vite" },
  integrations: [
    react(),
    {
      name: "bound-inputs",
      hooks: {
        "astro:build:start": () => {
          if (!input || !out)
            throw new Error("SITE_INPUT_DIR and ASTRO_OUT_DIR required");
        },
        "astro:build:done": () => {
          const receipt = JSON.parse(
            readFileSync(input + "/receipt.json", "utf8"),
          );
          const current = JSON.parse(
            execFileSync(
              process.env.PYTHON || "python3",
              [
                "-c",
                "import json; from project_tools.site_identity import input_identity; print(json.dumps(input_identity()))",
              ],
              { cwd: root, encoding: "utf8" },
            ),
          );
          if (JSON.stringify(receipt.identity) !== JSON.stringify(current))
            throw new Error("stale extracted source identity");
          writeFileSync(out + "/renderer-input.json", JSON.stringify(current));
        },
      },
    },
  ],
});

import { createServer } from "node:http";
import { readFile, stat, mkdir, writeFile } from "node:fs/promises";
import { resolve, sep } from "node:path";
import { spawn } from "node:child_process";
const root = resolve(process.env.SITE_DIR || "");
const base = process.env.SITE_BASE || "/quant-backtest-engine/";
const output = process.env.BROWSER_OUTPUT_DIR;
if (!process.env.SITE_DIR || !output)
  throw Error("SITE_DIR and BROWSER_OUTPUT_DIR required");
const mime = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".xml": "application/xml",
};
const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, "http://localhost");
    const name = decodeURIComponent(url.pathname);
    if (!name.startsWith(base)) {
      res.writeHead(404).end();
      return;
    }
    let path = resolve(root, name.slice(base.length));
    if (path !== root && !path.startsWith(root + sep)) {
      res.writeHead(403).end();
      return;
    }
    if ((await stat(path)).isDirectory()) path = resolve(path, "index.html");
    const bytes = await readFile(path);
    const ext = path.slice(path.lastIndexOf("."));
    res
      .writeHead(200, {
        "content-type": mime[ext] || "application/octet-stream",
      })
      .end(bytes);
  } catch {
    res.writeHead(404).end();
  }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const port = server.address().port;
await mkdir(output, { recursive: true });
await mkdir(output + "/tmp", { recursive: true });
await writeFile(
  output + "/server-receipt.json",
  JSON.stringify(
    {
      base,
      port,
      site: root,
      scope: "actual assembled static artifact; no dev server",
    },
    null,
    2,
  ),
);
try {
  const code = await new Promise((resolve) => {
    const child = spawn(
      process.execPath,
      ["node_modules/@playwright/test/cli.js", "test"],
      {
        cwd: new URL("../../", import.meta.url),
        stdio: "inherit",
        env: {
          ...process.env,
          TMPDIR: output + "/tmp",
          PLAYWRIGHT_BASE_URL: `http://127.0.0.1:${port}${base}`,
        },
      },
    );
    child.on("exit", resolve);
  });
  process.exitCode = code ?? 1;
} finally {
  await new Promise((r) => server.close(r));
}

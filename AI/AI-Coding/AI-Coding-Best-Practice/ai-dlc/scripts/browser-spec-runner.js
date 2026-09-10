#!/usr/bin/env node
/* scripts/browser-spec-runner.js — the deterministic half of P1-7.
 *
 * The MCP exploration path answers "what does this page look like?";
 * this runner answers "do the recorded assertions still hold" — no
 * model, no MCP, one isolated browser profile per attempt, a trace per
 * failed attempt, JSON out. It resolves playwright-core from the
 * pinned Playwright tree (AI_DLC_PLAYWRIGHT_ROOT, default
 * /opt/playwright-mcp) — no dependency is added, the pin already
 * carries the core.
 *
 * usage: node browser-spec-runner.js <spec.json> <out.json> <tracesDir>
 * spec: {pages: [{path?: "repo-relative", url?: "...", title?: "...",
 *                 selectors?: ["..."], texts?: ["..."]}]}
 * out:  {pages: [{url, attempts: [{ok, failures: []}],
 *                 trace: "path or null"}]}
 */
const fs = require("fs");
const os = require("os");
const path = require("path");

const [, , specPath, outPath, tracesDir] = process.argv;
if (!specPath || !outPath || !tracesDir) {
  console.error("usage: node browser-spec-runner.js <spec.json> " +
                "<out.json> <tracesDir>");
  process.exit(2);
}
const root = process.env.AI_DLC_PLAYWRIGHT_ROOT || "/opt/playwright-mcp";
let chromium;
try {
  chromium = require(path.join(root, "node_modules", "playwright-core"))
    .chromium;
} catch (e) {
  fs.writeFileSync(outPath, JSON.stringify({
    error: "playwright-core not resolvable from " + root + ": " + e.message,
  }));
  process.exit(0);
}
fs.mkdirSync(tracesDir, { recursive: true });
const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
const repoRoot = process.env.AI_DLC_SPEC_REPO_ROOT || process.cwd();

async function attempt(page, ctx, entry) {
  const failures = [];
  const target = entry.url
    || "file://" + path.resolve(repoRoot, entry.path);
  const pg = await ctx.newPage();
  try {
    const resp = await pg.goto(target, { waitUntil: "domcontentloaded",
                                         timeout: 15000 });
    if (resp && resp.status() >= 400) {
      failures.push("status " + resp.status());
    }
    if (entry.title && (await pg.title()) !== entry.title) {
      failures.push("title mismatch: " + (await pg.title()));
    }
    for (const sel of entry.selectors || []) {
      if ((await pg.locator(sel).count()) === 0) {
        failures.push("selector missing: " + sel);
      }
    }
    const body = await pg.content();
    for (const text of entry.texts || []) {
      if (!body.includes(text)) {
        failures.push("text missing: " + text);
      }
    }
  } catch (e) {
    failures.push("error: " + e.message);
  } finally {
    await pg.close();
  }
  return { ok: failures.length === 0, failures };
}

(async () => {
  const out = { pages: [] };
  for (const entry of spec.pages || []) {
    const rec = { url: entry.url || entry.path, attempts: [], trace: null };
    for (let i = 0; i < 2; i += 1) {
      // an isolated profile per attempt — session state never leaks
      // between attempts, let alone between runs
      // an isolated context per attempt (launch + fresh context, never
      // a reused profile): session state never leaks between attempts
      const browser = await chromium.launch({
        headless: true,
        // the plane runs as root; chromium's own sandbox refuses that
        // and dies at launch — the systemd boundary is outside this box
        chromiumSandbox: false,
        args: ["--no-sandbox"],
      });
      const ctx = await browser.newContext();
      await ctx.tracing.start({ screenshots: true, snapshots: true });
      const res = await attempt(entry, ctx, entry);
      const first = rec.attempts.length === 0;
      if (!res.ok && first) {
        const trace = path.join(tracesDir,
          "trace-" + (entry.path || entry.url || "page")
            .replace(/[^A-Za-z0-9._-]+/g, "_") + "-" + i + ".zip");
        await ctx.tracing.stop({ path: trace });
        rec.trace = trace;
      } else {
        await ctx.tracing.stop();
      }
      await ctx.close();
      await browser.close();
      rec.attempts.push(res);
      if (res.ok) break;       // pass on first attempt: one attempt is enough
    }
    out.pages.push(rec);
  }
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
  process.exit(0);
})().catch((e) => {
  fs.writeFileSync(outPath, JSON.stringify({ error: String(e) }));
  process.exit(0);
});

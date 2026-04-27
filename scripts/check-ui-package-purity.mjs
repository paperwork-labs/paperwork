#!/usr/bin/env node
/**
 * CI gate: @paperwork-labs/ui must stay framework-agnostic and browser-safe.
 * Catches imports, process.env, and unguarded window.* (see README).
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const uiSrc = path.join(__dirname, "..", "packages", "ui", "src");

const IMPORT_CALL_RE = /\bimport\s*\(\s*["']([^"']+)["']\s*\)/g;
const REQUIRE_RE = /\brequire\s*\(\s*["']([^"']+)["']\s*\)/g;

const USE_SERVER = /^\s*["']use server["'];?\s*$/;
const EXPORT_ASYNC = /^\s*export\s+async\s+function\s+/;
const EXPORT_DEFAULT_ASYNC = /^\s*export\s+default\s+async\s+function\s+/;
const PROCESS_ENV = /\bprocess\.env\b/;
/** window.foo or window['foo'] — allows typeof window */
const WINDOW_ACCESS = /\bwindow\s*(?:\.|\[)/;

/** @type {Array<{ file: string; line: number; message: string }>} */
const violations = [];

/**
 * @param {string} spec
 * @returns {string | null} reason or null if allowed
 */
function bannedImportReason(spec) {
  if (!spec) return null;
  if (spec === "next" || spec.startsWith("next/")) {
    return "import from Next.js (`next` / `next/*`) — colocate in apps/<name>/";
  }
  if (spec === "next-auth" || spec.startsWith("next-auth/")) {
    return "import from `next-auth` — colocate in apps/<name>/ or an auth package";
  }
  if (spec.startsWith("node:")) {
    return "import from `node:*` — not allowed in @paperwork-labs/ui";
  }
  if (spec === "fs" || spec === "path" || spec === "child_process") {
    return `import from Node built-in \`${spec}\` — not allowed in @paperwork-labs/ui`;
  }
  if (spec.startsWith("@vercel/")) {
    return "import from `@vercel/*` — colocate in app or infra package";
  }
  if (spec === "vite" || spec.startsWith("vite/")) {
    return "import from `vite` — colocate in app or tooling";
  }
  if (spec.startsWith("@remix-run/")) {
    return "import from `@remix-run/*` — colocate in the host app";
  }
  if (spec.startsWith("react-router")) {
    return "import from `react-router` — colocate in the host app";
  }
  return null;
}

/**
 * @param {string} line
 * @param {(spec: string) => string | null} onSpec
 */
function scanLineForImports(line, onSpec) {
  let m;
  const reFrom = /(?:^|\s)from\s+["']([^"']+)["']/;
  const m1 = line.match(reFrom);
  if (m1) {
    const r = onSpec(m1[1]);
    if (r) return r;
  }
  const reExportFrom = /\sfrom\s+["']([^"']+)["']\s*;?\s*$/;
  const m2 = line.match(/export\s+[\s\S]*?\sfrom\s+["']([^"']+)["']/);
  if (m2) {
    const r = onSpec(m2[1]);
    if (r) return r;
  }
  IMPORT_CALL_RE.lastIndex = 0;
  while ((m = IMPORT_CALL_RE.exec(line)) !== null) {
    const r = onSpec(m[1]);
    if (r) return r;
  }
  REQUIRE_RE.lastIndex = 0;
  while ((m = REQUIRE_RE.exec(line)) !== null) {
    const r = onSpec(m[1]);
    if (r) return r;
  }
  return null;
}

/**
 * @param {string} filePath
 * @param {string} content
 */
function scanFile(filePath, content) {
  const lines = content.split(/\n/);
  const rel = path.relative(path.join(__dirname, ".."), filePath);
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i] ?? "";
    const n = i + 1;

    const importReason = scanLineForImports(line, bannedImportReason);
    if (importReason) {
      violations.push({ file: rel, line: n, message: importReason });
    }

    if (USE_SERVER.test(line)) {
      violations.push({
        file: rel,
        line: n,
        message: '"use server" directive — not allowed in @paperwork-labs/ui',
      });
    }
    if (EXPORT_ASYNC.test(line) || EXPORT_DEFAULT_ASYNC.test(line)) {
      violations.push({
        file: rel,
        line: n,
        message:
          "export async function / export default async function — not allowed in @paperwork-labs/ui",
      });
    }
    if (PROCESS_ENV.test(line)) {
      violations.push({
        file: rel,
        line: n,
        message:
          "direct `process.env` access — pass config via props/context from the host app",
      });
    }
    if (WINDOW_ACCESS.test(line)) {
      violations.push({
        file: rel,
        line: n,
        message:
          "direct `window` access — guard with `typeof window !== \"undefined\"`, use `globalThis`, or pass via props",
      });
    }
  }
}

/**
 * @param {string} dir
 */
function walk(dir) {
  for (const name of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, name.name);
    if (name.isDirectory()) {
      walk(full);
    } else if (/\.(ts|tsx)$/.test(name.name)) {
      scanFile(full, fs.readFileSync(full, "utf8"));
    }
  }
}

if (!fs.existsSync(uiSrc)) {
  console.error(`check-ui-package-purity: missing ${uiSrc}`);
  process.exit(1);
}
walk(uiSrc);

if (violations.length) {
  console.error(
    "packages/ui purity check failed (framework-agnostic guardrails):\n"
  );
  for (const v of violations) {
    console.error(`${v.file}:${v.line} — ${v.message}`);
  }
  process.exit(1);
}
console.log("check-ui-package-purity: ok");

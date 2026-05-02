#!/usr/bin/env node
/**
 * Backfill Brain memory by ingesting Cursor agent JSONL transcripts one-by-one.
 *
 * Scans `TRANSCRIPT_ROOT` (or --root), excluding anything under `subagents/`.
 *
 * Required env:
 * - BRAIN_API_URL — base URL with or without trailing /api/v1
 * - BRAIN_API_SECRET — X-Brain-Secret for admin routes
 *
 * Optional:
 * - TRANSCRIPT_ROOT — override default transcript directory
 *
 * Flags: --dry-run, --root <dir>
 *
 * Run: pnpm backfill:transcripts
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const _UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const DEFAULT_TRANSCRIPT_ROOT = path.join(
  os.homedir(),
  ".cursor/projects/Users-paperworklabs-development-paperwork/agent-transcripts",
);

type BrainEnvelope<T> = {
  success: boolean;
  data?: T;
  error?: string | null;
};

type IngestResultPayload = {
  transcript_id: string;
  episodes_created: number;
  skipped?: boolean;
  errors?: string[];
};

function sanitizeEnv(val: string | undefined): string {
  if (!val) return "";
  return val.trim().replace(/\\n$/, "").replace(/\/+$/, "");
}

function brainApiV1Root(): string | null {
  const raw = sanitizeEnv(process.env.BRAIN_API_URL);
  if (!raw) return null;
  return raw.endsWith("/api/v1") ? raw : `${raw}/api/v1`;
}

function requireBrainEnv(): { base: string; secret: string } {
  const base = brainApiV1Root();
  const secret = sanitizeEnv(process.env.BRAIN_API_SECRET);
  if (!base) {
    console.error(
      "Missing BRAIN_API_URL. Set it to your Brain API base (e.g. https://example.com).",
    );
    process.exit(1);
  }
  if (!secret) {
    console.error("Missing BRAIN_API_SECRET (admin shared secret).");
    process.exit(1);
  }
  return { base, secret };
}

function parseArgs(argv: string[]): {
  dryRun: boolean;
  rootOverride: string | null;
} {
  let dryRun = false;
  let rootOverride: string | null = null;
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === "--dry-run") dryRun = true;
    else if (argv[i] === "--root") {
      const next = argv[++i];
      if (!next) {
        console.error("--root requires a directory argument");
        process.exit(1);
      }
      rootOverride = next;
    }
  }
  return { dryRun, rootOverride };
}

function transcriptRoot(cliRoot: string | null): string {
  if (cliRoot) return path.resolve(cliRoot);
  const env = sanitizeEnv(process.env.TRANSCRIPT_ROOT);
  if (env) return path.resolve(env);
  return DEFAULT_TRANSCRIPT_ROOT;
}

/** Walk tree; skip `subagents` directories entirely. Collect *.jsonl paths sorted. */
function discoverJsonlFiles(rootDir: string): string[] {
  const out: string[] = [];
  const walk = (dir: string): void => {
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      if (e.name === "subagents" && e.isDirectory()) continue;
      const full = path.join(dir, e.name);
      if (e.isDirectory()) walk(full);
      else if (e.isFile() && e.name.endsWith(".jsonl")) out.push(full);
    }
  };
  try {
    const st = fs.statSync(rootDir);
    if (st.isDirectory()) walk(rootDir);
  } catch {
    /* missing root */
  }
  return out.sort((a, b) => a.localeCompare(b));
}

function uuidFromTranscriptPath(filePath: string): string | null {
  const stem = path.basename(filePath, ".jsonl");
  return _UUID_RE.test(stem) ? stem : null;
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function isRetriableStatus(status: number): boolean {
  return status === 429 || status === 502 || status === 503 || status === 504;
}

async function ingestOneWithRetries(
  url: string,
  secret: string,
  filePath: string,
): Promise<
  | { ok: true; body: IngestResultPayload }
  | { ok: false; status: number; detail: string }
> {
  const payload = JSON.stringify({ file_path: filePath });
  let lastDetail = "unknown error";

  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Brain-Secret": secret,
        },
        body: payload,
      });
      const raw = await res.text();
      let envelope: BrainEnvelope<IngestResultPayload>;
      try {
        envelope = JSON.parse(raw) as BrainEnvelope<IngestResultPayload>;
      } catch {
        lastDetail = `invalid JSON (${res.status}): ${raw.slice(0, 200)}`;
        if (attempt < 2 && isRetriableStatus(res.status)) {
          await sleep(500 * (attempt + 1));
          continue;
        }
        return { ok: false, status: res.status, detail: lastDetail };
      }

      if (
        !res.ok ||
        !envelope.success ||
        envelope.data === undefined ||
        envelope.data === null
      ) {
        lastDetail = envelope.error ?? raw.slice(0, 400);
        if (attempt < 2 && isRetriableStatus(res.status)) {
          await sleep(500 * (attempt + 1));
          continue;
        }
        return { ok: false, status: res.status, detail: lastDetail };
      }

      return { ok: true, body: envelope.data };
    } catch (err) {
      lastDetail = err instanceof Error ? err.message : String(err);
      if (attempt < 2) {
        await sleep(500 * (attempt + 1));
        continue;
      }
      return { ok: false, status: 0, detail: `network: ${lastDetail}` };
    }
  }

  return { ok: false, status: 0, detail: lastDetail };
}

async function main(): Promise<void> {
  const { dryRun, rootOverride } = parseArgs(process.argv);
  const brainCreds = dryRun ? null : requireBrainEnv();
  const root = transcriptRoot(rootOverride);

  const files = discoverJsonlFiles(root);
  const total = files.length;

  if (total === 0) {
    console.log(`No .jsonl transcripts under ${root} (dir missing or empty).`);
    return;
  }

  console.log(`Transcript root: ${root}`);
  console.log(`Found ${total} transcript file(s) (subagents/ excluded).`);

  if (dryRun) {
    for (const fp of files) {
      const id = uuidFromTranscriptPath(fp);
      console.log(
        `  [dry-run] ${id ?? path.basename(fp)} — ${fp}`,
      );
    }
    console.log("\nDry run complete; no API calls made.");
    return;
  }

  const { base, secret } = brainCreds!;
  const url = `${base}/admin/transcripts/ingest`;

  let ingested = 0;
  let skipped = 0;
  let errors = 0;
  const failed: { path: string; transcriptId: string; detail: string }[] = [];

  for (let i = 0; i < files.length; i++) {
    const fp = path.resolve(files[i]);
    const tid = uuidFromTranscriptPath(fp) ?? path.basename(fp);
    process.stdout.write(`\rIngesting ${i + 1} of ${total} transcripts...`);
    const result = await ingestOneWithRetries(url, secret, fp);
    if (!result.ok) {
      errors += 1;
      failed.push({ path: fp, transcriptId: tid, detail: result.detail });
      continue;
    }
    if (result.body.skipped) skipped += 1;
    else ingested += 1;
  }

  process.stdout.write("\r" + " ".repeat(60) + "\r");

  console.log("—".repeat(48));
  console.log(`Total found:           ${total}`);
  console.log(`Successfully ingested: ${ingested}`);
  console.log(`Already existed:       ${skipped}`);
  console.log(`Errors:                ${errors}`);

  if (failed.length) {
    console.log("\nFailed transcripts:");
    for (const f of failed) {
      console.log(`  • ${f.transcriptId}`);
      console.log(`    ${f.path}`);
      console.log(`    ${f.detail}`);
    }
  }
}

const invoked = fileURLToPath(import.meta.url);
const entry = process.argv[1] && path.resolve(process.argv[1]);
if (entry === invoked) {
  main().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}

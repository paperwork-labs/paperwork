#!/usr/bin/env node
/**
 * Backfill Brain transcripts via POST /admin/transcripts/ingest-batch (server-side scan).
 *
 * Simpler than backfill-transcripts.ts: Brain recursively discovers *.jsonl (includes
 * subagents/ unless changed server-side).
 *
 * Required env: BRAIN_API_URL, BRAIN_API_SECRET
 * Optional: TRANSCRIPT_ROOT, or pass --root <dir>
 *
 * Flags: --dry-run, --root <dir>
 */

import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_TRANSCRIPT_ROOT = path.join(
  os.homedir(),
  ".cursor/projects/Users-paperworklabs-development-paperwork/agent-transcripts",
);

type BrainEnvelope<T> = {
  success: boolean;
  data?: T;
  error?: string | null;
};

type BatchResultPayload = {
  scanned_files: number;
  ingested_files: number;
  skipped_files: number;
  total_episodes_created: number;
  errors: string[];
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

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function isRetriableStatus(status: number): boolean {
  return status === 429 || status === 502 || status === 503 || status === 504;
}

async function postIngestBatchWithRetries(
  url: string,
  secret: string,
  directory: string,
): Promise<
  | { ok: true; body: BatchResultPayload }
  | { ok: false; status: number; detail: string }
> {
  const payload = JSON.stringify({ directory });
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
      let envelope: BrainEnvelope<BatchResultPayload>;
      try {
        envelope = JSON.parse(raw) as BrainEnvelope<BatchResultPayload>;
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
  const root = transcriptRoot(rootOverride);

  console.log(`Transcript root (batch scan): ${root}`);

  if (dryRun) {
    console.log(
      "[dry-run] Would POST /admin/transcripts/ingest-batch with this directory.",
    );
    console.log("No API calls made.");
    return;
  }

  const { base, secret } = requireBrainEnv();
  const url = `${base}/admin/transcripts/ingest-batch`;

  const result = await postIngestBatchWithRetries(url, secret, root);
  if (!result.ok) {
    console.error(`Batch ingest failed: ${result.detail}`);
    process.exit(1);
  }

  const b = result.body;
  console.log("—".repeat(48));
  console.log(`Scanned files:           ${b.scanned_files}`);
  console.log(`Ingested files:          ${b.ingested_files}`);
  console.log(`Skipped (already had):   ${b.skipped_files}`);
  console.log(`Total episodes created:  ${b.total_episodes_created}`);
  if (b.errors.length) {
    console.log(`\nPer-file errors (${b.errors.length}):`);
    for (const line of b.errors) console.log(`  • ${line}`);
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

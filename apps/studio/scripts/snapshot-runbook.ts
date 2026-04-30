/**
 * Build-time snapshot of docs/strategy/DAY_0_FOUNDER_ACTIONS.md.
 * Writes apps/studio/src/data/runbook-snapshot.json with the same
 * RunbookData shape that day0-runbook.ts serves at runtime.
 *
 * Run via: tsx scripts/snapshot-runbook.ts
 * Auto-run during: prebuild (see package.json)
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const STUDIO_ROOT = path.join(__dirname, "..");
const REPO_ROOT = path.join(STUDIO_ROOT, "..", "..");
const MD_PATH = path.join(REPO_ROOT, "docs/strategy/DAY_0_FOUNDER_ACTIONS.md");
const OUT_PATH = path.join(STUDIO_ROOT, "src/data/runbook-snapshot.json");

type RunbookItem = {
  id: number;
  task: string;
  time: string;
  unblocks: string;
  done: boolean;
};

type RunbookSection = {
  title: string;
  items: RunbookItem[];
};

type RunbookSnapshot = {
  sections: RunbookSection[];
  total: number;
  completed: number;
  remaining: number;
  estTimeLeftMin: number;
  generatedFrom: string;
};

function parseMinutes(raw: string): number {
  const h = raw.match(/(\d+)\s*hr/);
  const m = raw.match(/(\d+)\s*min/);
  let total = 0;
  if (h) total += parseInt(h[1], 10) * 60;
  if (m) total += parseInt(m[1], 10);
  return total;
}

function parseRow(row: string): RunbookItem | null {
  const cells = row
    .split("|")
    .map((c) => c.trim())
    .filter(Boolean);
  if (cells.length < 5) return null;
  const id = parseInt(cells[0], 10);
  if (Number.isNaN(id)) return null;
  return {
    id,
    task: cells[1],
    time: cells[2],
    unblocks: cells[3],
    done: cells[4] === "☑",
  };
}

function run(): void {
  if (!fs.existsSync(MD_PATH)) {
    process.stderr.write(`snapshot-runbook: source file not found: ${MD_PATH}\n`);
    process.exit(1);
  }

  const raw = fs.readFileSync(MD_PATH, "utf-8");
  const lines = raw.split("\n");

  const sections: RunbookSection[] = [];
  let currentSection: RunbookSection | null = null;

  for (const line of lines) {
    const headingMatch = line.match(/^##\s+(.+)/);
    if (headingMatch) {
      const title = headingMatch[1].trim();
      currentSection = { title, items: [] };
      sections.push(currentSection);
      continue;
    }
    if (line.startsWith("|") && currentSection) {
      const item = parseRow(line);
      if (item) currentSection.items.push(item);
    }
  }

  const populated = sections.filter((s) => s.items.length > 0);
  const allItems = populated.flatMap((s) => s.items);
  const completed = allItems.filter((i) => i.done).length;
  const remaining = allItems.length - completed;
  const estTimeLeftMin = allItems
    .filter((i) => !i.done)
    .reduce((sum, i) => sum + parseMinutes(i.time), 0);

  const snapshot: RunbookSnapshot = {
    sections: populated,
    total: allItems.length,
    completed,
    remaining,
    estTimeLeftMin,
    generatedFrom: "docs/strategy/DAY_0_FOUNDER_ACTIONS.md",
  };

  fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true });
  fs.writeFileSync(OUT_PATH, JSON.stringify(snapshot, null, 2) + "\n");
  process.stdout.write(`snapshot-runbook: wrote ${OUT_PATH} (${allItems.length} items)\n`);
}

run();

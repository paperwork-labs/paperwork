import fs from "node:fs";
import path from "node:path";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type RunbookItem = {
  id: number;
  task: string;
  time: string;
  unblocks: string;
  done: boolean;
};

export type RunbookSection = {
  title: string;
  items: RunbookItem[];
};

export type RunbookData = {
  sections: RunbookSection[];
  total: number;
  completed: number;
  remaining: number;
  estTimeLeftMin: number;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert a human time string like "1hr", "30min", "5min" to minutes. */
function parseMinutes(raw: string): number {
  const h = raw.match(/(\d+)\s*hr/);
  const m = raw.match(/(\d+)\s*min/);
  let total = 0;
  if (h) total += parseInt(h[1], 10) * 60;
  if (m) total += parseInt(m[1], 10);
  return total;
}

/**
 * Parse a single markdown table row into a RunbookItem.
 * Expected format: | # | Action | Time | Unblocks | ☐/☑ |
 */
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

// ---------------------------------------------------------------------------
// Main parser
// ---------------------------------------------------------------------------

export function parseDay0Runbook(): RunbookData {
  const mdPath = path.resolve(
    process.cwd(),
    "docs/strategy/DAY_0_FOUNDER_ACTIONS.md",
  );

  // Fallback: monorepo root might differ from cwd in Next.js dev vs build.
  let raw: string;
  try {
    raw = fs.readFileSync(mdPath, "utf-8");
  } catch {
    // Try from repo root relative to this file's compiled location.
    const altPath = path.resolve(
      __dirname,
      "../../../../docs/strategy/DAY_0_FOUNDER_ACTIONS.md",
    );
    raw = fs.readFileSync(altPath, "utf-8");
  }

  const lines = raw.split("\n");

  const sections: RunbookSection[] = [];
  let currentSection: RunbookSection | null = null;

  for (const line of lines) {
    // Detect section headings (## lines).
    const headingMatch = line.match(/^##\s+(.+)/);
    if (headingMatch) {
      const title = headingMatch[1].trim();
      currentSection = { title, items: [] };
      sections.push(currentSection);
      continue;
    }

    // Parse table rows (skip header / separator rows).
    if (line.startsWith("|") && currentSection) {
      const item = parseRow(line);
      if (item) currentSection.items.push(item);
    }
  }

  // Remove sections with no items (e.g. the top-level title).
  const populated = sections.filter((s) => s.items.length > 0);

  const allItems = populated.flatMap((s) => s.items);
  const completed = allItems.filter((i) => i.done).length;
  const remaining = allItems.length - completed;
  const estTimeLeftMin = allItems
    .filter((i) => !i.done)
    .reduce((sum, i) => sum + parseMinutes(i.time), 0);

  return {
    sections: populated,
    total: allItems.length,
    completed,
    remaining,
    estTimeLeftMin,
  };
}

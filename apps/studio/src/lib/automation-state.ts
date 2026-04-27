import { readFile } from "fs/promises";
import { join } from "path";

const GH = "https://github.com/paperwork-labs/paperwork";

export type AutomationRow = {
  name: string;
  nameHref: string | null;
  type: string;
  schedule: string;
  owner: string;
  status: string;
  what: string;
  flag: string;
  studio: string;
  studioHref: string | null;
};

function firstMdLink(cell: string): { text: string; href: string | null } {
  const t = cell.trim();
  const m = /^\[([^\]]*)\]\(([^)]+)\)/.exec(t);
  if (m) {
    const href = m[2].trim();
    return {
      text: m[1].trim() || t,
      href: href.length > 0 ? href : null,
    };
  }
  return { text: t, href: null };
}

function parseStudioCell(cell: string): { label: string; href: string | null } {
  const t = cell.trim();
  if (t === "—" || t === "-") {
    return { label: "—", href: null };
  }
  const link = firstMdLink(t);
  return { label: link.text, href: link.href };
}

/** Best-effort parse of the main table in docs/infra/AUTOMATION_STATE.md */
export function parseAutomationTable(markdown: string): AutomationRow[] {
  const lines = markdown.split(/\r?\n/);
  const start = lines.findIndex(
    (l) => l.includes("| Name ") && l.includes("Type"),
  );
  if (start === -1) {
    return [];
  }
  const rows: AutomationRow[] = [];
  for (let i = start + 2; i < lines.length; i += 1) {
    const raw = lines[i];
    const line = raw.trim();
    if (!line) {
      continue;
    }
    if (line.startsWith("## ")) {
      break;
    }
    if (!line.startsWith("|")) {
      break;
    }
    if (line.includes("---|")) {
      continue;
    }
    const parts = line
      .split("|")
      .map((c) => c.trim())
      .filter((_c, idx, arr) => idx > 0 && idx < arr.length - 1);
    if (parts.length < 8) {
      continue;
    }
    const [name, type, schedule, owner, status, what, flag, studio] = parts;
    if (name === "Name" || name.startsWith("**Tally**")) {
      continue;
    }
    const n = firstMdLink(name);
    const s = parseStudioCell(studio);
    rows.push({
      name: n.text,
      nameHref: n.href,
      type,
      schedule,
      owner,
      status,
      what,
      flag,
      studio: s.label,
      studioHref: s.href,
    });
  }
  return rows;
}

export async function readAutomationStateMarkdown(): Promise<string | null> {
  const candidates = [
    join(process.cwd(), "..", "..", "docs", "infra", "AUTOMATION_STATE.md"),
    join(process.cwd(), "docs", "infra", "AUTOMATION_STATE.md"),
  ];
  for (const p of candidates) {
    try {
      return await readFile(p, "utf-8");
    } catch {
      // try next
    }
  }
  return null;
}

export function defaultDocLinkForName(name: string, nameHref: string | null): string {
  if (nameHref) {
    return nameHref;
  }
  const key = name.trim().toLowerCase();
  if (key === "pr_sweep" || key.includes("sprint_planner") || key.includes("brain_")) {
    return `${GH}/tree/main/apis/brain/app/schedulers`;
  }
  if (key.includes("workflow") || key.endsWith(".yaml)")) {
    return `${GH}/tree/main/.github/workflows`;
  }
  return `${GH}/blob/main/docs/infra/AUTOMATION_STATE.md`;
}

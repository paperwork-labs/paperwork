import type { DispatchRecord, EaRoutingRow, MarkdownTable, PrOutcomeRecord } from "./personas-types";

export function extractModelAssignmentSection(markdownBody: string): string | null {
  const match = markdownBody.match(/^## Model Assignment\s*$/im);
  if (!match || match.index === undefined) return null;
  const after = markdownBody.slice(match.index + match[0].length);
  const nextHdr = after.search(/^## /m);
  const section = nextHdr === -1 ? after : after.slice(0, nextHdr);
  const t = section.trim();
  return t.length ? t : null;
}

export function extractMainHeading(content: string): string | null {
  const m = content.match(/^#\s+(.+)$/m);
  return m?.[1]?.trim() ?? null;
}

export function parseEstRangeUsd(cell: string): number | null {
  const explicitPair = cell.match(/\$\s*([\d.]+)\s*[–—-]\s*\$\s*([\d.]+)/);
  if (explicitPair) {
    const a = Number(explicitPair[1]);
    const b = Number(explicitPair[2]);
    if (Number.isFinite(a) && Number.isFinite(b)) return (a + b) / 2;
  }
  const compactRange = cell.match(/\$\s*([\d.]+)\s*[–—-]\s*([\d.]+)/);
  if (compactRange) {
    const a = Number(compactRange[1]);
    const b = Number(compactRange[2]);
    if (Number.isFinite(a) && Number.isFinite(b)) return (a + b) / 2;
  }
  const single = cell.match(/\$\s*([\d.]+)/);
  return single ? Number(single[1]) : null;
}

/** Rough mid-band $/run from AI_MODEL_REGISTRY “Est. $ / run” column text, keyed by persona slug. */
export function parsePersonaEstCostPerRunUsd(registryMd: string): Map<string, number> {
  const map = new Map<string, number>();
  const tableBlock = registryMd.match(
    /### Brain PersonaSpec[\s\S]*?(?=### |\n## [^#]|\n---\n\n## |$)/,
  );
  if (!tableBlock) return map;
  const lines = tableBlock[0].split("\n").filter((l) => l.startsWith("|"));
  for (const line of lines) {
    const cells = line
      .split("|")
      .map((c) => c.trim())
      .filter(Boolean);
    if (cells.length < 5 || cells[0].toLowerCase().includes("persona")) continue;
    const persona = cells[0].toLowerCase().replace(/\*/g, "").trim();
    const est = cells[cells.length - 1];
    const mid = parseEstRangeUsd(est);
    if (mid !== null) map.set(persona, mid);
  }
  return map;
}

export function avgTokensFromOutcomes(outcomes: PrOutcomeRecord[]): number | null {
  let sum = 0;
  let n = 0;
  for (const o of outcomes) {
    const ti = typeof o.tokens_input === "number" ? o.tokens_input : null;
    const to = typeof o.tokens_output === "number" ? o.tokens_output : null;
    if (ti !== null || to !== null) {
      sum += (ti ?? 0) + (to ?? 0);
      n += 1;
    }
  }
  if (n === 0) return null;
  return sum / n;
}

export function dispatchPersonaId(d: DispatchRecord): string | null {
  const raw =
    (typeof d.persona_slug === "string" && d.persona_slug.trim()) ||
    (typeof d.persona === "string" && d.persona.trim()) ||
    (typeof d.persona_pin === "string" && d.persona_pin.trim());
  return raw ? raw.trim().toLowerCase() : null;
}

export function parseEaTagRouting(eaMarkdown: string): EaRoutingRow[] {
  const tableRows = parseCanonicalTagTable(eaMarkdown);
  const overrides = parseSmartPersonaRoutingTags(eaMarkdown);
  const merged: EaRoutingRow[] = [];
  for (const row of tableRows) {
    const o = overrides.get(row.tag);
    merged.push({
      tag: row.tag,
      routingTarget: o ?? inferTargetFromRole(row.role),
    });
  }
  return merged;
}

function parseCanonicalTagTable(md: string): { tag: string; role: string }[] {
  const lines = md.split("\n");
  const rows: { tag: string; role: string }[] = [];
  let inTable = false;
  for (const line of lines) {
    if (line.includes("| Historical Slack channel") && line.includes("Canonical tag")) {
      inTable = true;
      continue;
    }
    if (!inTable) continue;
    if (!line.trim().startsWith("|")) break;
    if (/^\|[\s\-:|]+\|$/.test(line.replace(/\s/g, ""))) continue;
    const cells = line
      .split("|")
      .map((c) => c.trim())
      .filter((c) => c.length > 0);
    if (cells.length < 4) continue;
    const tagCell = cells[2]?.replace(/^`|`$/g, "").trim() ?? "";
    const role = cells[3] ?? "";
    if (!tagCell || tagCell.toLowerCase() === "canonical tag") continue;
    rows.push({ tag: tagCell, role });
  }
  return rows;
}

function parseSmartPersonaRoutingTags(md: string): Map<string, string> {
  const map = new Map<string, string>();
  const idx = md.indexOf("### Smart Persona Routing");
  if (idx === -1) return map;
  const rest = md.slice(idx);
  const end = rest.search(/\n### /);
  const section = end === -1 ? rest : rest.slice(0, end);
  const re = /`([^`]+)`\s*(?:→|->)\s*([^,\n]+)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(section)) !== null) {
    const tag = m[1].trim();
    let target = m[2].trim();
    target = target.replace(/\*\*/g, "").trim();
    map.set(tag, normalizeRoutingTarget(target));
  }
  return map;
}

function normalizeRoutingTarget(raw: string): string {
  const s = raw.trim();
  const lower = s.toLowerCase();
  if (lower.includes("engineering")) return "engineering";
  if (lower.includes("strategy")) return "strategy";
  if (lower.includes("social")) return "social";
  if (lower.includes("cpa") || lower.includes("tax")) return "cpa / tax-domain";
  if (lower.includes("qa")) return "qa";
  if (lower.includes("ea") || lower.includes("operator")) return "ea";
  return s;
}

function inferTargetFromRole(role: string): string {
  const r = role.toLowerCase();
  if (r.includes("ea ") || r.startsWith("ea ") || r.includes("briefing")) return "ea";
  if (r.includes("strategy") || r.includes("decision")) return "strategy";
  if (r.includes("engineering") || r.includes("deploy")) return "engineering";
  if (r.includes("social")) return "social";
  if (r.includes("tax") || r.includes("cpa")) return "cpa";
  if (r.includes("trading")) return "trading";
  if (r.includes("alert")) return "engineering / qa";
  return "ea (default)";
}

function pipeRowCells(line: string): string[] {
  return line
    .trim()
    .split("|")
    .map((c) => c.trim())
    .filter((c) => c.length > 0);
}

export function parseMarkdownTables(md: string): MarkdownTable[] {
  const lines = md.split("\n");
  const tables: MarkdownTable[] = [];
  let currentTitle = "";
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith("### ")) {
      currentTitle = line.replace(/^###\s+/, "").trim();
    } else if (line.startsWith("## ")) {
      currentTitle = line.replace(/^##\s+/, "").trim();
    }
    const next = lines[i + 1];
    if (!line.includes("|") || !next || !/^\|[\s\-:|]+\|/.test(next.trim())) {
      continue;
    }

    const headers = pipeRowCells(line).filter((c) => !/^:?-+:?$/ .test(c));
    if (headers.length === 0 || headers.every((h) => /^:?-+:?$/ .test(h))) continue;

    i += 2;
    const rowData: string[][] = [];
    while (i < lines.length) {
      const rowLine = lines[i];
      if (!rowLine.includes("|")) break;
      if (/^\|[\s\-:|]+\|$/ .test(rowLine.trim())) break;
      const cells = pipeRowCells(rowLine);
      if (cells.length === headers.length) rowData.push(cells);
      i += 1;
    }
    i -= 1;
    if (rowData.length) {
      tables.push({ title: currentTitle || "Table", headers, rows: rowData });
    }
  }
  return tables;
}

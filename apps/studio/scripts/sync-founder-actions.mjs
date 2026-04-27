/**
 * Reads docs/infra/FOUNDER_ACTIONS.md and writes src/data/founder-actions.json
 * for the admin Founder Actions page. Run from apps/studio via prebuild.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const STUDIO_ROOT = path.join(__dirname, "..");
const REPO_ROOT = path.join(STUDIO_ROOT, "..", "..");
const MD = path.join(REPO_ROOT, "docs/infra/FOUNDER_ACTIONS.md");
const OUT = path.join(STUDIO_ROOT, "src/data/founder-actions.json");

function stripFrontMatter(s) {
  if (!s.startsWith("---\n")) return s;
  const end = s.indexOf("\n---\n", 4);
  if (end === -1) return s;
  return s.slice(end + 5);
}

function extractRunbookHref(sourceLine) {
  if (!sourceLine) {
    return "https://github.com/paperwork-labs/paperwork/blob/main/docs/infra/FOUNDER_ACTIONS.md";
  }
  const mdLink = sourceLine.match(/\]\((docs\/[^)]+\.md[^)]*)\)/);
  if (mdLink) {
    const rel = mdLink[1].split("#")[0];
    return `https://github.com/paperwork-labs/paperwork/blob/main/${rel}`;
  }
  const m = sourceLine.match(/`([^`]+\.(md|mdx|tsx|ts|json|yaml|yml))`/);
  if (m) {
    const rel = m[1].replace(/^\s*/, "");
    return `https://github.com/paperwork-labs/paperwork/blob/main/${rel}`;
  }
  const pr = sourceLine.match(/PR #(\d+)/i);
  if (pr) {
    return `https://github.com/paperwork-labs/paperwork/pull/${pr[1]}`;
  }
  return "https://github.com/paperwork-labs/paperwork/blob/main/docs/infra/FOUNDER_ACTIONS.md";
}

function parseItemBlock(body) {
  const lines = body.split("\n");
  const fields = {
    why: "",
    where: "",
    steps: [],
    verification: "",
    source: "",
    eta: "",
  };
  let mode = null;
  for (const line of lines) {
    if (line.startsWith("- **Why this matters:**")) {
      mode = "why";
      fields.why = line.replace(/^- \*\*Why this matters:\*\*\s*/i, "").trim();
      continue;
    }
    if (line.startsWith("- **Where:**")) {
      mode = "where";
      fields.where = line.replace(/^- \*\*Where:\*\*\s*/i, "").trim();
      continue;
    }
    if (line.startsWith("- **Steps:**")) {
      mode = "steps";
      continue;
    }
    if (line.startsWith("- **Verification:**")) {
      mode = "verification";
      fields.verification = line.replace(/^- \*\*Verification:\*\*\s*/i, "").trim();
      continue;
    }
    if (line.startsWith("- **Source:**")) {
      mode = "source";
      fields.source = line.replace(/^- \*\*Source:\*\*\s*/i, "").trim();
      continue;
    }
    if (line.startsWith("- **ETA:**")) {
      mode = "eta";
      fields.eta = line.replace(/^- \*\*ETA:\*\*\s*/i, "").trim();
      continue;
    }
    if (line.startsWith("- **Note:**")) {
      if (!fields.why) {
        fields.why = line.replace(/^- \*\*Note:\*\*\s*/i, "").trim();
      }
      continue;
    }
    if (mode === "steps" && /^\s*\d+\./.test(line)) {
      fields.steps.push(line.trim());
    }
  }
  return fields;
}

const TIER_MAP = {
  "pending — critical (blocks production)": "critical",
  "pending — operational (blocks automation)": "operational",
  "pending — branding / polish (cosmetic)": "branding",
};

function main() {
  if (!fs.existsSync(MD)) {
    console.warn("sync-founder-actions: missing", MD, "— writing empty payload");
    fs.writeFileSync(
      OUT,
      JSON.stringify(
        {
          generated: new Date().toISOString(),
          tiers: [],
          resolved: [],
          counts: { critical: 0, operational: 0, branding: 0, totalPending: 0 },
        },
        null,
        2
      ) + "\n"
    );
    return;
  }

  const raw = fs.readFileSync(MD, "utf8");
  const md = stripFrontMatter(raw);

  const tierHeaders = [
    { marker: "## Pending — Critical (blocks production)\n", id: "critical", label: "Pending — Critical" },
    { marker: "## Pending — Operational (blocks automation)\n", id: "operational", label: "Pending — Operational" },
    { marker: "## Pending — Branding / Polish (cosmetic)\n", id: "branding", label: "Pending — Branding" },
  ];

  const resolvedMarker = "## Resolved\n";
  const futureMarker = "## Future / strategy";
  const tiers = [];
  const resolved = [];

  for (const th of tierHeaders) {
    const start = md.indexOf(th.marker);
    if (start === -1) continue;
    const from = start + th.marker.length;
    const next = [
      ...tierHeaders
        .filter((x) => x.marker !== th.marker)
        .map((x) => md.indexOf(x.marker, from))
        .filter((i) => i !== -1),
      md.indexOf(resolvedMarker, from),
      md.indexOf(futureMarker, from),
    ]
      .filter((i) => i !== -1)
      .sort((a, b) => a - b);
    const end = next.length ? next[0] : md.length;
    const section = md.slice(from, end);
    const parts = section.split(/(?=^### )/m).filter((p) => p.trim().startsWith("###"));
    const items = [];
    for (const part of parts) {
      const firstNl = part.indexOf("\n");
      const head = firstNl === -1 ? part : part.slice(0, firstNl);
      const m = head.match(/^###\s*[\d.]+\s*(.+)$/);
      if (!m) continue;
      const title = m[1].trim();
      const body = firstNl === -1 ? "" : part.slice(firstNl + 1);
      const f = parseItemBlock(body);
      items.push({
        title,
        runbookUrl: extractRunbookHref(f.source),
        why: f.why,
        where: f.where,
        steps: f.steps,
        verification: f.verification,
        source: f.source,
        eta: f.eta,
      });
    }
    tiers.push({ id: th.id, label: th.label, items });
  }

  const rStart = md.indexOf(resolvedMarker);
  if (rStart !== -1) {
    const rFrom = rStart + resolvedMarker.length;
    const rEnd = md.indexOf("\n## ", rFrom + 1);
    const rSection = md.slice(
      rFrom,
      rEnd === -1 ? md.length : rEnd
    );
    for (const line of rSection.split("\n")) {
      const t = line.trim();
      if (t.startsWith("- ")) resolved.push(t.slice(2).trim());
    }
  }

  let critical = 0;
  let operational = 0;
  let branding = 0;
  for (const t of tiers) {
    const n = t.items.length;
    if (t.id === "critical") critical = n;
    if (t.id === "operational") operational = n;
    if (t.id === "branding") branding = n;
  }
  const totalPending = critical + operational + branding;

  const out = {
    generated: new Date().toISOString(),
    sourceFile: "docs/infra/FOUNDER_ACTIONS.md",
    tiers,
    resolved,
    counts: { critical, operational, branding, totalPending },
  };
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(out, null, 2) + "\n");
  console.log("sync-founder-actions: wrote", OUT, "counts", out.counts);
}

main();

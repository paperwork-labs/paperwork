/**
 * Pre-processes sprint markdown / brief fragments before render so GitHub- and
 * editor-shaped bodies don't collapse (tables, fences, runaway newlines).
 */

export function normalizeSprintSource(markdown: string): string {
  if (!markdown || typeof markdown !== "string") {
    return "";
  }

  let t = markdown.replace(/\r\n/g, "\n").trim();

  if (t.length === 0) {
    return "";
  }

  // Collapse 3+ blank lines to 2 to avoid huge vertical gaps; keep one empty line between blocks
  t = t.replace(/\n{3,}/g, "\n\n");

  // Ensure tables have a proper blank line before (GFM) when line starts with |
  t = t.replace(/([^\n])\n(\|[^|\n]+)/g, "$1\n\n$2");

  // Close common partial fences if an odd number of ``` exists (heuristic)
  const fence = /```/g;
  const matches = [...t.matchAll(fence)];
  if (matches.length % 2 === 1) {
    t = `${t}\n\`\`\`\n`;
  }

  // Trim trailing spaces per line
  t = t
    .split("\n")
    .map((l) => l.replace(/[ \t]+$/g, ""))
    .join("\n");

  return t.trimEnd();
}

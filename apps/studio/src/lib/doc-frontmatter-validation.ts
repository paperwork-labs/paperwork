import yaml from "js-yaml";

export const STUDIO_DOC_FRONTMATTER_KEYS = [
  "owner",
  "last_reviewed",
  "doc_kind",
  "domain",
  "status",
] as const;

export type StudioDocFrontmatterKey = (typeof STUDIO_DOC_FRONTMATTER_KEYS)[number];

export type FrontmatterValidationResult = {
  warnings: string[];
  missingRequired: StudioDocFrontmatterKey[];
  canSave: boolean;
  data: Record<string, unknown>;
  parseError: string | null;
};

/** Validates the YAML body between --- delimiters (not including delimiters). */
export function validateStudioDocFrontmatter(frontmatterYaml: string): FrontmatterValidationResult {
  const trimmed = frontmatterYaml.trim();
  if (!trimmed) {
    const missingRequired = [...STUDIO_DOC_FRONTMATTER_KEYS];
    return {
      warnings: missingRequired.map((k) => `Missing frontmatter field: ${k}`),
      missingRequired,
      canSave: false,
      data: {},
      parseError: "Frontmatter is empty.",
    };
  }

  let data: Record<string, unknown>;
  try {
    data = yaml.load(trimmed) as Record<string, unknown>;
    if (data === null || typeof data !== "object" || Array.isArray(data)) {
      throw new Error("Frontmatter must be a YAML mapping.");
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Invalid YAML.";
    return {
      warnings: [`Could not parse frontmatter: ${msg}`],
      missingRequired: [...STUDIO_DOC_FRONTMATTER_KEYS],
      canSave: false,
      data: {},
      parseError: msg,
    };
  }

  const missingRequired: StudioDocFrontmatterKey[] = [];
  for (const key of STUDIO_DOC_FRONTMATTER_KEYS) {
    const v = data[key];
    if (v === undefined || v === null || (typeof v === "string" && !v.trim())) {
      missingRequired.push(key);
    }
  }

  const warnings = missingRequired.map((k) => `Missing or empty frontmatter field: ${k}`);

  return {
    warnings,
    missingRequired,
    canSave: missingRequired.length === 0,
    data,
    parseError: null,
  };
}

export function composeStudioDocFile(frontmatterYaml: string, bodyMarkdown: string): string {
  const block = frontmatterYaml.trimEnd();
  const body = bodyMarkdown.replace(/^\n+/, "");
  return `---\n${block}\n---\n\n${body}`;
}

/** Split raw markdown file into inner frontmatter YAML (no ---) and body. */
export function splitDocRaw(raw: string): { front: string; body: string } {
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!m) {
    return { front: "", body: raw };
  }
  return { front: m[1] ?? "", body: m[2] ?? "" };
}

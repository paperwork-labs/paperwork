/**
 * Shared parsers for wiki-style doc links ([[slug]] / [[runbook:x]] / [[ws:x]]), markdown
 * links to other indexed docs, and @mentions.
 * Used by the knowledge-graph build script and Studio doc backlinks rail.
 */

const WIKI_BLOCK = /\[\[([^\]]+)\]\]/g;

function slugifyWikiLabel(raw: string): string {
  return raw.trim().replace(/_/g, "-").replace(/\s+/g, "-").toLowerCase();
}

export type ExtractedDocRelations = {
  /** Lowercase hyphenated slug targets inferred from wiki links [[...]]. */
  docSlugs: string[];
  runbooks: Array<{ raw: string; slugGuess: string }>;
  workstreams: string[];
  personas: string[];
};

export type ExtractDocRelationsOpts = {
  /** Index `path` for the source file (e.g. `docs/BRAIN_ARCHITECTURE.md`). */
  sourcePath?: string;
  /** Map from index `path` to doc `slug` (all indexed docs). */
  pathToSlug?: Map<string, string>;
};

function posixDirname(p: string): string {
  const norm = p.replace(/\\/g, "/").replace(/\/+\s*$/, "");
  const i = norm.lastIndexOf("/");
  if (i <= 0) return "";
  return norm.slice(0, i);
}

function posixNormalizePathSegments(parts: string[]): string {
  const stack: string[] = [];
  for (const part of parts) {
    if (part === "" || part === ".") continue;
    if (part === "..") stack.pop();
    else stack.push(part);
  }
  return stack.join("/");
}

/** Resolve a relative / absolute `.md` href to a repo-relative path like `docs/foo/bar.md`. */
export function resolveMarkdownHrefToIndexedPath(sourcePath: string, href: string): string | null {
  const h = href.trim();
  if (!h) return null;
  if (/^[a-z][a-z0-9+.-]*:/i.test(h)) return null;
  const noFrag = h.split("#")[0] ?? "";
  const clean = (noFrag.split("?")[0] ?? "").trim().replace(/\\/g, "/");
  if (!/\.md$/i.test(clean)) return null;

  const joined = clean.startsWith("/")
    ? clean.replace(/^\/+/, "")
    : posixNormalizePathSegments(
        `${posixDirname(sourcePath)}/${clean}`.split("/").filter(Boolean),
      );

  return joined || null;
}

function classifyWiki(inner: string): {
  docSlug?: string;
  runbook?: string;
  workstream?: string;
} | null {
  const head = inner.split("|")[0]?.split("#")[0]?.trim() ?? "";
  if (!head) return null;
  if (/^runbook:\s*/i.test(head)) {
    const rest = head.replace(/^runbook:\s*/i, "").trim();
    return { runbook: rest };
  }
  const wsMatch = head.match(/^ws:\s*(ws-\d+)\s*$/i);
  if (wsMatch) return { workstream: wsMatch[1]!.toUpperCase() };

  if (head.includes(":")) return null;
  return { docSlug: slugifyWikiLabel(head) };
}

const MARKDOWN_LINK_HREF = /\[[^\]]*]\(([^)]+)\)/g;

/**
 * Reads markdown body **without** YAML frontmatter.
 * When `sourcePath` and `pathToSlug` are passed, also resolves internal markdown links to indexed slugs.
 */
export function extractDocRelations(
  markdownBody: string,
  opts?: ExtractDocRelationsOpts,
): ExtractedDocRelations {
  const docSlugsSet = new Set<string>();
  const runbooks: Array<{ raw: string; slugGuess: string }> = [];
  const workstreamsSet = new Set<string>();
  const personasSet = new Set<string>();

  markdownBody.replace(WIKI_BLOCK, (_, innerRaw: string) => {
    const typed = classifyWiki(innerRaw);
    if (typed?.runbook) {
      const slugGuess = slugifyWikiLabel(
        typed.runbook.replace(/^runbook\//i, "").replace(/^runbooks\//i, ""),
      );
      runbooks.push({ raw: typed.runbook, slugGuess });
    } else if (typed?.workstream) {
      workstreamsSet.add(typed.workstream);
    } else if (typed?.docSlug) {
      docSlugsSet.add(typed.docSlug);
    }
    return "";
  });

  const src = opts?.sourcePath?.trim();
  const pathToSlug = opts?.pathToSlug;
  if (src && pathToSlug?.size) {
    let lm: RegExpExecArray | null;
    MARKDOWN_LINK_HREF.lastIndex = 0;
    while ((lm = MARKDOWN_LINK_HREF.exec(markdownBody)) !== null) {
      const hrefRaw = lm[1]?.trim() ?? "";
      if (!hrefRaw || hrefRaw.startsWith("<")) continue;
      const resolved = resolveMarkdownHrefToIndexedPath(src, hrefRaw);
      if (!resolved) continue;
      const slug = pathToSlug.get(resolved);
      if (slug) docSlugsSet.add(slug);
    }
  }

  const personaRe = /\B@([a-z][a-z0-9-]*(?:\/[a-z0-9-]+)?)/gi;
  let pm: RegExpExecArray | null;
  while ((pm = personaRe.exec(markdownBody)) !== null) {
    personasSet.add(pm[1]!.toLowerCase());
  }

  return {
    docSlugs: [...docSlugsSet].sort(),
    runbooks,
    workstreams: [...workstreamsSet].sort(),
    personas: [...personasSet].sort(),
  };
}

export function slugToKnowledgeNodeId(slug: string): string {
  return slug.replace(/-/g, "_").toUpperCase();
}

export function knowledgeNodeIdToSlugGuess(id: string): string {
  return id.toLowerCase().replace(/_/g, "-");
}

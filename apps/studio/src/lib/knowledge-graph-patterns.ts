/**
 * Shared parsers for wiki-style doc links ([[slug]] / [[runbook:x]] / [[ws:x]]) and @mentions.
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

/**
 * Reads markdown body **without** YAML frontmatter.
 */
export function extractDocRelations(markdownBody: string): ExtractedDocRelations {
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

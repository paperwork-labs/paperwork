import { DocsHubClient } from "./docs-hub-client";
import { loadDocHubEntries } from "@/lib/docs";
import { getReadingPathsWithResolvedDocs } from "@/lib/reading-paths";

export const dynamic = "force-static";
export const revalidate = 300;

export default function DocsHubPage() {
  const entries = loadDocHubEntries();
  const readingPaths = getReadingPathsWithResolvedDocs().map((p) => ({
    id: p.id,
    title: p.title,
    est_minutes: p.est_minutes,
    resolvedCount: p.resolved.length,
    firstSlug: p.resolved[0]?.slug ?? null,
  }));

  return <DocsHubClient entries={entries} readingPaths={readingPaths} />;
}

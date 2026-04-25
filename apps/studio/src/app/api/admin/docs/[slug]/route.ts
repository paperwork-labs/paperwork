import { NextResponse } from "next/server";

import { loadDocContent } from "@/lib/docs";

export const dynamic = "force-static";
export const revalidate = 300;

// Agent-readable raw-markdown endpoint for Track N. Keeps the Studio page
// (rich HTML) distinct from what Brain and other agents consume over HTTP.
export async function GET(
  _req: Request,
  { params }: { params: Promise<{ slug: string }> },
) {
  const { slug } = await params;
  const doc = loadDocContent(slug);
  if (!doc) {
    return NextResponse.json({ error: "doc not found" }, { status: 404 });
  }
  return NextResponse.json({
    slug,
    title: doc.entry.title,
    category: doc.entry.category,
    owners: doc.entry.owners,
    tags: doc.entry.tags,
    summary: doc.entry.summary,
    path: doc.entry.path,
    markdown: doc.markdown,
    wordCount: doc.wordCount,
    lastModified: doc.lastModified,
  });
}

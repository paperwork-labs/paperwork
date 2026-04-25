import { NextResponse } from "next/server";

import { loadDocsIndex, searchDocs } from "@/lib/docs";

export const dynamic = "force-static";
export const revalidate = 300;

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const q = searchParams.get("q");
  if (q && q.trim()) {
    return NextResponse.json({ query: q, results: searchDocs(q) });
  }
  const { entries, categories } = loadDocsIndex();
  return NextResponse.json({ categories, docs: entries });
}

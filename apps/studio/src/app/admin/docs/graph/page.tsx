import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { DocsKnowledgeGraphClient } from "./docs-knowledge-graph-client";
import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { getKnowledgeGraphVizPayload } from "@/lib/knowledge-graph-viz";

export const dynamic = "force-static";
export const revalidate = 300;

export default function DocsKnowledgeGraphPage() {
  const payload = getKnowledgeGraphVizPayload();

  return (
    <div className="space-y-6">
      <nav className="text-xs text-zinc-500">
        <Link href="/admin/docs" className="inline-flex items-center gap-1 hover:text-zinc-200">
          <ArrowLeft className="h-3.5 w-3.5" />
          All docs
        </Link>
      </nav>
      <HqPageHeader
        eyebrow="Knowledge"
        title="Knowledge graph"
        subtitle="Obsidian-style view of doc relationships. Node size reflects inbound links; dashed rose rings flag stale, highly-linked pages (hot zones)."
        breadcrumbs={[
          { label: "Docs", href: "/admin/docs" },
          { label: "Knowledge graph" },
        ]}
      />
      <DocsKnowledgeGraphClient payload={payload} />
    </div>
  );
}

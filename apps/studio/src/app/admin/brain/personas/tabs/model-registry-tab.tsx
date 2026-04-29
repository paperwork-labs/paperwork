"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";

import { Badge } from "@paperwork-labs/ui";

import { usePersonasInitial } from "../personas-client";

export function ModelRegistryTab() {
  const { modelRegistryMarkdown, modelRegistryLastReviewed } = usePersonasInitial();

  return (
    <div className="space-y-4">
      {modelRegistryLastReviewed ? (
        <Badge variant="secondary" className="border border-zinc-700 bg-zinc-900 text-zinc-200">
          Last reviewed: {modelRegistryLastReviewed}
        </Badge>
      ) : (
        <Badge variant="secondary" className="border border-zinc-700 bg-zinc-900 text-zinc-300">
          Last reviewed: unknown
        </Badge>
      )}
      <article className="prose prose-invert prose-sm max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
          {modelRegistryMarkdown.trim() || "_Model registry document is empty._"}
        </ReactMarkdown>
      </article>
    </div>
  );
}

"use client";

import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { normalizeSprintSource } from "@/lib/normalize-sprint-source";

const proseClass = [
  "prose prose-invert max-w-none prose-p:mb-2 prose-p:last:mb-0",
  "prose-headings:text-zinc-100 prose-a:text-sky-300 prose-a:no-underline hover:prose-a:text-sky-200",
  "prose-code:rounded prose-code:bg-zinc-800/60 prose-code:px-1 prose-code:py-0.5",
  "prose-pre:bg-zinc-950/80 prose-pre:border prose-pre:border-zinc-800",
  "prose-table:text-sm prose-th:border prose-td:border prose-th:border-zinc-800 prose-td:border-zinc-800",
  "prose-blockquote:border-l-amber-500/50 prose-blockquote:text-zinc-400",
  "text-sm leading-relaxed text-zinc-200",
].join(" ");

type Props = {
  children: string | null | undefined;
  className?: string;
};

export function SprintMarkdown({ children, className }: Props) {
  const raw = String(children ?? "");
  const text = normalizeSprintSource(raw);
  if (!text) return null;
  return (
    <div className={[proseClass, className].filter(Boolean).join(" ")}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
        {text}
      </ReactMarkdown>
    </div>
  );
}

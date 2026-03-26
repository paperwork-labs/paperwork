import * as React from "react"
import ReactMarkdown from "react-markdown"

import { cn } from "@/lib/utils"

export interface AgentMarkdownProps {
  content: string
  className?: string
}

/**
 * Renders agent analysis markdown with conservative styling (no raw HTML).
 */
export function AgentMarkdown({ content, className }: AgentMarkdownProps) {
  return (
    <div
      className={cn(
        "agent-markdown text-sm leading-relaxed text-card-foreground",
        "[&_p]:mb-2 last:[&_p]:mb-0",
        "[&_ul]:mb-2 [&_ul]:list-disc [&_ul]:pl-4",
        "[&_ol]:mb-2 [&_ol]:list-decimal [&_ol]:pl-4",
        "[&_li]:mt-0.5",
        "[&_strong]:font-semibold",
        "[&_code]:rounded-md [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-xs",
        "[&_pre]:my-2 [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:bg-muted [&_pre]:p-3 [&_pre]:text-xs",
        "[&_blockquote]:border-l-2 [&_blockquote]:border-muted-foreground/40 [&_blockquote]:pl-3 [&_blockquote]:italic [&_blockquote]:text-muted-foreground",
        "[&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2",
        className
      )}
    >
      <ReactMarkdown
        components={{
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium"
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

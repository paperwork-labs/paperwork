import Link from "next/link";
import type { Components } from "react-markdown";

import { resolveMarkdownHrefToIndexedPath } from "@/lib/knowledge-graph-patterns";

export type DocMarkdownComponentsOpts = {
  sourcePath: string;
  pathToSlug: Map<string, string>;
};

/**
 * Turn repo-relative markdown links into Studio viewer routes where we have matching pages.
 */
export function rewriteRepoFileMarkdownHref(rawHref: string): string | null {
  const trimmed = rawHref.trim();
  if (/^https?:\/\//i.test(trimmed) || trimmed.startsWith("mailto:")) {
    return null;
  }

  const hashIdx = trimmed.indexOf("#");
  const fragment = hashIdx >= 0 ? trimmed.slice(hashIdx) : "";
  const beforeHash = hashIdx >= 0 ? trimmed.slice(0, hashIdx) : trimmed;

  const qIdx = beforeHash.indexOf("?");
  const pathPart = (
    qIdx >= 0 ? beforeHash.slice(0, qIdx) : beforeHash
  ).replace(/\\/g, "/");

  const mdcTail = pathPart.match(/\.cursor\/rules\/([^/]+\.mdc)$/i);
  if (mdcTail) {
    return `/admin/.cursor/rules/${mdcTail[1]}${fragment}`;
  }

  const specTail = pathPart.match(/apis\/brain\/app\/personas\/specs\/([^/]+\.(?:yaml|yml))$/i);
  if (specTail) {
    return `/admin/apis/brain/app/personas/specs/${specTail[1]}${fragment}`;
  }

  return null;
}

export function createDocMarkdownComponents(opts: DocMarkdownComponentsOpts): Components {
  const { sourcePath, pathToSlug } = opts;
  return {
    table({ children, ...props }) {
      return (
        <div className="overflow-x-auto max-w-full">
          <table {...props}>{children}</table>
        </div>
      );
    },
    a({ href, children, className, ...rest }) {
      if (!href) return <span className={className}>{children}</span>;
      const stripped = href.trim();

      const studioHref = rewriteRepoFileMarkdownHref(stripped);
      if (studioHref) {
        return (
          <Link href={studioHref} className={className} {...rest}>
            {children}
          </Link>
        );
      }

      if (/^https?:\/\//i.test(stripped) || stripped.startsWith("mailto:")) {
        return (
          <a href={stripped} className={className} target="_blank" rel="noreferrer" {...rest}>
            {children}
          </a>
        );
      }

      const resolved = resolveMarkdownHrefToIndexedPath(sourcePath, stripped);
      if (resolved) {
        const targetSlug = pathToSlug.get(resolved);
        if (targetSlug) {
          return (
            <Link href={`/admin/docs/${targetSlug}`} className={className} {...rest}>
              {children}
            </Link>
          );
        }
      }
      return (
        <a href={stripped} className={className} {...rest}>
          {children}
        </a>
      );
    },
  };
}

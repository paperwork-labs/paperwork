import { notFound } from "next/navigation";

/** Fallback for unmatched `/admin/*` paths so `admin/not-found.tsx` renders inside the shell. */
export default function AdminUnmatchedSlugCatchAll(): never {
  notFound();
}

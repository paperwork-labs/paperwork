import { FileQuestion } from "lucide-react";

import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";

/** Segment `not-found` for unknown `/admin/*` routes. */
export default function AdminNotFound() {
  return (
    <div className="flex min-h-[min(520px,calc(100vh-12rem))] items-center justify-center py-12">
      <div className="w-full max-w-md">
        <HqEmptyState
          icon={<FileQuestion className="h-10 w-10" aria-hidden />}
          title="Page not found"
          description="This admin URL is not mapped. Return to the command center dashboard."
          action={{ label: "Back to admin", href: "/admin" }}
        />
      </div>
    </div>
  );
}

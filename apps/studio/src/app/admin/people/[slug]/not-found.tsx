import Link from "next/link";

import { UserX } from "lucide-react";

import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";

/** Shown when `notFound()` is triggered for unknown employee slugs. */
export default function EmployeeProfileNotFound() {
  return (
    <div className="flex min-h-[min(480px,calc(100vh-14rem))] items-center justify-center py-12">
      <div className="w-full max-w-md">
        <HqEmptyState
          icon={<UserX className="h-10 w-10" aria-hidden />}
          title="Employee not found"
          description="Brain has no roster entry for this slug. Return to People and choose another teammate."
          action={{ label: "Back to People", href: "/admin/people" }}
        />
        <p className="mt-6 text-center text-xs text-zinc-600">
          <Link href="/admin" className="text-zinc-500 hover:text-zinc-400">
            Admin home
          </Link>
        </p>
      </div>
    </div>
  );
}

import Link from "next/link";

import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";
import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";

export const dynamic = "force-dynamic";

export default function VendorsPage() {
  return (
    <div className="space-y-8">
      <HqPageHeader
        title="Vendors"
        subtitle="Central place for vendor relationships; full registry and API wiring land in follow-on work."
      />
      <HqEmptyState
        title="Vendor hub"
        description="Use the Infrastructure vendors tab for the live vendor matrix from Brain infra, or open Cost monitor for spend."
        action={{
          label: "Open vendor matrix",
          href: "/admin/infrastructure?tab=vendors",
        }}
      />
      <p className="text-center text-xs text-zinc-500">
        <Link
          href="/admin/infrastructure?tab=cost"
          className="text-zinc-400 underline-offset-2 hover:text-zinc-200 hover:underline"
        >
          Cost monitor
        </Link>
      </p>
    </div>
  );
}

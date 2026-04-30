import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import circlesData from "@/data/circles.json";
import type { CirclesSeedFile } from "@/types/circles";

import { DelegatedAccessClient } from "./delegated-client";

export const dynamic = "force-static";

export const metadata = { title: "Delegated access — Studio" };

const data = circlesData as CirclesSeedFile;

export default function AdminDelegatedPage() {
  return (
    <div className="space-y-8" data-testid="admin-delegated-page">
      <HqPageHeader
        title="Delegated access"
        subtitle="Active shares granted to accountants and other delegates"
        breadcrumbs={[
          { label: "Admin", href: "/admin" },
          { label: "Delegated access" },
        ]}
      />

      <DelegatedAccessClient shares={data.delegated_shares} />
    </div>
  );
}

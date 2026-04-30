import { Users } from "lucide-react";

import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import circlesData from "@/data/circles.json";
import type { Circle, CirclesSeedFile } from "@/types/circles";

export const dynamic = "force-static";

export const metadata = { title: "Circles — Studio" };

const data = circlesData as CirclesSeedFile;

const CIRCLE_TYPE_LABEL: Record<Circle["type"], string> = {
  household: "Household",
  family: "Family",
  partners: "Partners",
};

function circleTypeLabel(type: Circle["type"]): string {
  return CIRCLE_TYPE_LABEL[type];
}

export default function AdminCirclesPage() {
  return (
    <div className="space-y-8" data-testid="admin-circles-page">
      <HqPageHeader
        title="Circles"
        subtitle="Households and shared groups — seed data until backend wiring"
        breadcrumbs={[
          { label: "Admin", href: "/admin" },
          { label: "Circles" },
        ]}
      />

      <ul className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
        {data.circles.map((circle) => (
          <li key={circle.id}>
            <article
              data-testid={`circle-card-${circle.id}`}
              className="flex h-full flex-col rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-5 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
                    {circleTypeLabel(circle.type)}
                  </p>
                  <h2 className="mt-1 truncate text-lg font-semibold text-zinc-100">
                    {circle.name}
                  </h2>
                  <p className="mt-1 text-xs text-zinc-500">
                    Created by {circle.created_by} ·{" "}
                    <time dateTime={circle.created_at}>
                      {circle.created_at.slice(0, 10)}
                    </time>
                  </p>
                </div>
              </div>

              <div className="mt-4 border-t border-zinc-800/80 pt-4">
                <p className="mb-2 flex items-center gap-2 text-xs font-medium text-zinc-400">
                  <Users className="h-3.5 w-3.5 shrink-0 text-zinc-500" aria-hidden />
                  Members ({circle.members.length})
                </p>
                <ul className="space-y-2" data-testid={`circle-members-${circle.id}`}>
                  {circle.members.map((m) => (
                    <li
                      key={m.user_id}
                      className="flex items-center justify-between gap-2 rounded-lg bg-zinc-950/50 px-3 py-2 text-sm"
                    >
                      <span className="min-w-0 truncate text-zinc-200">{m.display_name}</span>
                      <span
                        className={`shrink-0 rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                          m.role === "owner"
                            ? "border-emerald-500/35 bg-emerald-500/10 text-emerald-200"
                            : "border-zinc-600 bg-zinc-800/80 text-zinc-400"
                        }`}
                      >
                        {m.role}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </article>
          </li>
        ))}
      </ul>
    </div>
  );
}

"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ChevronRight, MapPin } from "lucide-react";
import { Badge, Card, CardContent } from "@paperwork-labs/ui";
import type {
  FormationDashboardStatus,
  FormationSummary,
} from "@/lib/dashboard-formations";

const statusBadgeClass: Record<FormationDashboardStatus, string> = {
  draft:
    "border-slate-600 bg-slate-800/80 text-slate-300 hover:bg-slate-800/80",
  pending:
    "border-amber-500/40 bg-amber-500/10 text-amber-200 hover:bg-amber-500/10",
  submitted:
    "border-sky-500/40 bg-sky-500/10 text-sky-200 hover:bg-sky-500/10",
  confirmed:
    "border-emerald-500/40 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/10",
  failed:
    "border-red-500/40 bg-red-500/10 text-red-200 hover:bg-red-500/10",
};

const statusLabel: Record<FormationDashboardStatus, string> = {
  draft: "Draft",
  pending: "Pending",
  submitted: "Submitted",
  confirmed: "Confirmed",
  failed: "Failed",
};

function formatCreatedAt(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export interface FormationCardProps {
  formation: FormationSummary;
  index?: number;
}

export function FormationCard({ formation, index = 0 }: FormationCardProps) {
  const { id, llcName, stateCode, status, createdAt } = formation;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.06 }}
    >
      <Link href={`/dashboard/${id}`} className="group block focus-visible:outline-none">
        <Card
          className="border-slate-800 bg-slate-900/50 transition-colors hover:border-teal-500/30 hover:bg-slate-900/80 focus-visible:ring-2 focus-visible:ring-teal-400/50"
        >
          <CardContent className="flex items-center gap-4 p-4 sm:p-5">
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="truncate text-base font-semibold text-slate-50 sm:text-lg">
                  {llcName}
                </h2>
                <Badge
                  variant="outline"
                  className={statusBadgeClass[status]}
                >
                  {statusLabel[status]}
                </Badge>
              </div>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-400">
                <span className="inline-flex items-center gap-1.5">
                  <MapPin className="size-3.5 shrink-0 text-teal-400/90" aria-hidden />
                  {stateCode}
                </span>
                <span>Started {formatCreatedAt(createdAt)}</span>
              </div>
            </div>
            <ChevronRight
              className="size-5 shrink-0 text-slate-500 transition-transform group-hover:translate-x-0.5 group-hover:text-teal-400"
              aria-hidden
            />
          </CardContent>
        </Card>
      </Link>
    </motion.div>
  );
}

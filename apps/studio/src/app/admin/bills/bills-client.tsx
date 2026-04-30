"use client";

import { useMemo } from "react";

import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";
import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import { HqStatCard } from "@/components/admin/hq/HqStatCard";
import {
  BILL_STATUS_LABELS,
  type Bill,
  type BillStatus,
  type BillsListPage,
} from "@/types/bills";

const STATUS_STYLES: Record<BillStatus, string> = {
  pending: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  approved: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  paid: "bg-sky-500/15 text-sky-300 ring-sky-500/30",
  rejected: "bg-zinc-500/15 text-zinc-400 ring-zinc-500/30",
};

function formatUsd(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

function kpisFromBills(items: Bill[]) {
  const pending = items.filter((b) => b.status === "pending");
  const approved = items.filter((b) => b.status === "approved");
  const paid = items.filter((b) => b.status === "paid");
  return {
    total: items.length,
    pendingUsd: pending.reduce((s, b) => s + b.amount_usd, 0),
    approvedUsd: approved.reduce((s, b) => s + b.amount_usd, 0),
    paidUsd: paid.reduce((s, b) => s + b.amount_usd, 0),
  };
}

export function BillsClient({ initialPage }: { initialPage: BillsListPage | null }) {
  const items = initialPage?.items ?? [];
  const kpis = useMemo(() => kpisFromBills(items), [items]);

  if (!initialPage) {
    return (
      <div className="rounded-xl border border-red-900/40 bg-red-500/5 p-8 text-center">
        <p className="text-sm font-medium text-red-400">Could not load bills</p>
        <p className="mt-1 text-xs text-red-500/70">Check Brain API configuration and try again.</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <HqPageHeader
        title="Bills"
        subtitle="Vendor invoices — pending, approval, payment, and reject flow (Brain ledger)."
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <HqStatCard variant="compact" label="Total bills" value={kpis.total} />
        <HqStatCard
          variant="compact"
          label="Pending (USD)"
          value={formatUsd(kpis.pendingUsd)}
          status="warning"
        />
        <HqStatCard
          variant="compact"
          label="Approved (USD)"
          value={formatUsd(kpis.approvedUsd)}
          status="success"
        />
        <HqStatCard variant="compact" label="Paid (USD)" value={formatUsd(kpis.paidUsd)} />
      </div>

      {items.length === 0 ? (
        <HqEmptyState
          title="No bills yet"
          description="Create bills via the Brain API or a future composer. The ledger starts empty."
        />
      ) : (
        <ul className="space-y-2" aria-label="Bills list">
          {items.map((bill) => {
            const statusStyle = STATUS_STYLES[bill.status] ?? STATUS_STYLES.pending;
            return (
              <li
                key={bill.id}
                className="flex flex-col gap-2 rounded-lg border border-zinc-800/60 bg-zinc-900/40 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-zinc-100">
                    Vendor{" "}
                    <span className="font-mono text-xs text-zinc-400">{bill.vendor_id}</span>
                  </p>
                  {bill.description ? (
                    <p className="mt-0.5 truncate text-xs text-zinc-500">{bill.description}</p>
                  ) : null}
                  <p className="mt-1 text-xs text-zinc-500">
                    Due <span className="tabular-nums">{bill.due_date}</span>
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">
                  <span
                    className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ring-1 ${statusStyle}`}
                  >
                    {BILL_STATUS_LABELS[bill.status]}
                  </span>
                  <span className="text-sm font-semibold tabular-nums text-zinc-100">
                    {formatUsd(bill.amount_usd)}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

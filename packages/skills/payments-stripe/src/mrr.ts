import type { CustomerSubscription, MRRSnapshot } from "./types.js";

const MRR_STATUSES: ReadonlySet<CustomerSubscription["status"]> = new Set([
  "active",
  "past_due",
]);

function assertSingleCurrency(
  amounts: { value: number; currency: string }[],
): string {
  if (amounts.length === 0) {
    return "USD";
  }
  const ccy = amounts[0]!.currency.toUpperCase();
  for (const a of amounts) {
    if (a.currency.toUpperCase() !== ccy) {
      throw new Error(
        `Mixed-currency subscriptions are not supported for MRR aggregation (expected ${ccy}, got ${a.currency}).`,
      );
    }
  }
  return ccy;
}

type StripeItemLike = {
  quantity?: number | null;
  price?: {
    unit_amount?: number | null;
    currency?: string | null;
    recurring?: {
      interval?: string;
      interval_count?: number | null;
    } | null;
  } | null;
};

type StripeSubLike = {
  items?: { data?: StripeItemLike[] };
};

/** Convert recurring price to monthly minor units (cents). */
export function monthlyMinorFromStripeItems(
  sub: StripeSubLike,
): { value: number; currency: string } {
  const items = sub.items?.data ?? [];
  if (items.length === 0) {
    return { value: 0, currency: "USD" };
  }

  const parts: { value: number; currency: string }[] = [];
  for (const line of items) {
    const qty = line.quantity ?? 1;
    const price = line.price;
    if (!price?.currency) {
      continue;
    }
    const unit = price.unit_amount ?? 0;
    const raw = unit * qty;
    const interval = price.recurring?.interval ?? "month";
    const intervalCount = Math.max(1, price.recurring?.interval_count ?? 1);
    let monthly = raw;
    switch (interval) {
      case "month":
        monthly = raw / intervalCount;
        break;
      case "year":
        monthly = raw / (12 * intervalCount);
        break;
      case "week":
        monthly = (raw * 52) / (12 * intervalCount);
        break;
      case "day":
        monthly = (raw * 365) / (12 * intervalCount);
        break;
      default:
        monthly = raw / intervalCount;
    }
    parts.push({
      value: Math.round(monthly),
      currency: price.currency.toUpperCase(),
    });
  }

  if (parts.length === 0) {
    return { value: 0, currency: "USD" };
  }

  const currency = assertSingleCurrency(parts);
  const value = parts.reduce((sum, p) => sum + p.value, 0);
  return { value, currency };
}

export function mapStripeSubscriptionStatus(
  status: string | undefined,
): CustomerSubscription["status"] {
  switch (status) {
    case "active":
      return "active";
    case "trialing":
      return "trialing";
    case "past_due":
    case "unpaid":
      return "past_due";
    case "canceled":
    case "incomplete_expired":
      return "cancelled";
    default:
      return "trialing";
  }
}

/**
 * Point-in-time MRR from normalized subscriptions. New / expansion / contraction / churn
 * buckets are reserved for event-driven reporting; list-based snapshots set them to zero.
 */
export function snapshotMrrFromSubscriptions(
  subs: CustomerSubscription[],
  asOf: Date = new Date(),
): MRRSnapshot {
  const contributing = subs.filter((s) => MRR_STATUSES.has(s.status));
  const ccy = assertSingleCurrency(contributing.map((s) => s.amount));
  const total = contributing.reduce((sum, s) => sum + s.amount.value, 0);
  const customerCount = new Set(contributing.map((s) => s.customerId)).size;
  const zero = { value: 0, currency: ccy };

  return {
    asOf,
    totalMrr: { value: total, currency: ccy },
    customerCount,
    newMrr: zero,
    expansionMrr: zero,
    contractionMrr: zero,
    churnedMrr: zero,
  };
}

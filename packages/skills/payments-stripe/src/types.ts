export type StripeConfig = {
  secretKey: string;
  webhookSecret: string;
};

export type SubscriptionEvent = {
  type:
    | "subscription.created"
    | "subscription.updated"
    | "subscription.deleted"
    | "invoice.paid"
    | "invoice.failed";
  customerId: string;
  subscriptionId?: string;
  amount?: { value: number; currency: string };
  occurredAt: Date;
  raw: unknown;
};

export type MRRSnapshot = {
  asOf: Date;
  totalMrr: { value: number; currency: string };
  customerCount: number;
  newMrr: { value: number; currency: string };
  expansionMrr: { value: number; currency: string };
  contractionMrr: { value: number; currency: string };
  churnedMrr: { value: number; currency: string };
};

export type CustomerSubscription = {
  customerId: string;
  subscriptionId: string;
  startedAt: Date;
  cancelledAt?: Date;
  amount: { value: number; currency: string };
  status: "active" | "trialing" | "cancelled" | "past_due";
};

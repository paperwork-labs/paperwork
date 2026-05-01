import Stripe from "stripe";

import {
  mapStripeSubscriptionStatus,
  monthlyMinorFromStripeItems,
  snapshotMrrFromSubscriptions,
} from "./mrr.js";
import type {
  CustomerSubscription,
  MRRSnapshot,
  StripeConfig,
  SubscriptionEvent,
} from "./types.js";
import { stripeCustomerId, verifyWebhook as verifyStripeWebhook } from "./webhooks.js";

export type {
  CustomerSubscription,
  MRRSnapshot,
  StripeConfig,
  SubscriptionEvent,
} from "./types.js";

export { handleEvent, verifyWebhook } from "./webhooks.js";
export {
  mapStripeSubscriptionStatus,
  monthlyMinorFromStripeItems,
  snapshotMrrFromSubscriptions,
} from "./mrr.js";

export function stripeSubscriptionToCustomerSubscription(
  sub: Stripe.Subscription,
): CustomerSubscription {
  const cancelledAt =
    sub.canceled_at != null ? new Date(sub.canceled_at * 1000) : undefined;

  return {
    customerId: stripeCustomerId(sub.customer),
    subscriptionId: sub.id,
    startedAt: new Date(sub.start_date * 1000),
    cancelledAt,
    amount: monthlyMinorFromStripeItems(sub),
    status: mapStripeSubscriptionStatus(sub.status),
  };
}

export class PaymentsStripeClient {
  private readonly stripe: Stripe;

  constructor(private readonly config: StripeConfig) {
    this.stripe = new Stripe(config.secretKey, {
      typescript: true,
    });
  }

  verifyWebhook(rawBody: string | Buffer, signature: string): SubscriptionEvent {
    return verifyStripeWebhook(this.config.webhookSecret, rawBody, signature);
  }

  async snapshotMrr(asOf?: Date): Promise<MRRSnapshot> {
    const stripeSubs = await this.fetchStripeSubscriptions();
    const mapped = stripeSubs.map(stripeSubscriptionToCustomerSubscription);
    return snapshotMrrFromSubscriptions(mapped, asOf ?? new Date());
  }

  async listSubscriptions(): Promise<CustomerSubscription[]> {
    const stripeSubs = await this.fetchStripeSubscriptions();
    return stripeSubs.map(stripeSubscriptionToCustomerSubscription);
  }

  private async fetchStripeSubscriptions(): Promise<Stripe.Subscription[]> {
    const out: Stripe.Subscription[] = [];
    for await (const sub of this.stripe.subscriptions.list({
      limit: 100,
      status: "all",
      expand: ["data.items.data.price"],
    })) {
      out.push(sub);
    }
    return out;
  }
}

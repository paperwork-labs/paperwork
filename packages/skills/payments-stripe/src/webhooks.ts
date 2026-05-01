import Stripe from "stripe";

import { monthlyMinorFromStripeItems } from "./mrr.js";
import type { SubscriptionEvent } from "./types.js";

export function stripeCustomerId(
  customer: string | Stripe.Customer | Stripe.DeletedCustomer | null,
): string {
  if (typeof customer === "string") {
    return customer;
  }
  if (customer && "deleted" in customer && customer.deleted) {
    throw new Error("Stripe customer reference is deleted; cannot resolve id.");
  }
  if (customer && "id" in customer && typeof customer.id === "string") {
    return customer.id;
  }
  throw new Error("Stripe object is missing customer id.");
}

function subscriptionBodyAmount(
  sub: Stripe.Subscription,
): { value: number; currency: string } {
  return monthlyMinorFromStripeItems(sub);
}

export function handleEvent(event: Stripe.Event): SubscriptionEvent {
  const occurredAt = new Date(event.created * 1000);

  switch (event.type) {
    case "customer.subscription.created": {
      const sub = event.data.object as Stripe.Subscription;
      return {
        type: "subscription.created",
        customerId: stripeCustomerId(sub.customer),
        subscriptionId: sub.id,
        amount: subscriptionBodyAmount(sub),
        occurredAt,
        raw: event,
      };
    }
    case "customer.subscription.updated": {
      const sub = event.data.object as Stripe.Subscription;
      return {
        type: "subscription.updated",
        customerId: stripeCustomerId(sub.customer),
        subscriptionId: sub.id,
        amount: subscriptionBodyAmount(sub),
        occurredAt,
        raw: event,
      };
    }
    case "customer.subscription.deleted": {
      const sub = event.data.object as Stripe.Subscription;
      return {
        type: "subscription.deleted",
        customerId: stripeCustomerId(sub.customer),
        subscriptionId: sub.id,
        amount: subscriptionBodyAmount(sub),
        occurredAt,
        raw: event,
      };
    }
    case "invoice.paid": {
      const inv = event.data.object as Stripe.Invoice;
      return {
        type: "invoice.paid",
        customerId: stripeCustomerId(inv.customer),
        subscriptionId:
          typeof inv.subscription === "string"
            ? inv.subscription
            : (inv.subscription?.id ?? undefined),
        amount: {
          value: inv.amount_paid,
          currency: (inv.currency ?? "usd").toUpperCase(),
        },
        occurredAt,
        raw: event,
      };
    }
    case "invoice.payment_failed": {
      const inv = event.data.object as Stripe.Invoice;
      return {
        type: "invoice.failed",
        customerId: stripeCustomerId(inv.customer),
        subscriptionId:
          typeof inv.subscription === "string"
            ? inv.subscription
            : (inv.subscription?.id ?? undefined),
        amount: {
          value: inv.amount_due,
          currency: (inv.currency ?? "usd").toUpperCase(),
        },
        occurredAt,
        raw: event,
      };
    }
    default:
      throw new Error(
        `Unsupported Stripe webhook type for subscription skill: ${event.type}`,
      );
  }
}

export function verifyWebhook(
  webhookSecret: string,
  rawBody: string | Buffer,
  signature: string,
): SubscriptionEvent {
  const event = Stripe.webhooks.constructEvent(rawBody, signature, webhookSecret);
  return handleEvent(event);
}

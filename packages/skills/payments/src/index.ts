export enum PaymentProvider {
  STRIPE = "STRIPE",
  PLAID = "PLAID",
}

export type PaymentEvent = {
  id: string;
  provider: PaymentProvider;
  amount: number;
  currency: string;
  status: string;
  timestamp: Date;
  metadata: Record<string, unknown>;
};

export class PaymentsClient {
  async getTransactions(since: Date): Promise<PaymentEvent[]> {
    throw new Error("Not implemented");
  }

  async getBalance(): Promise<{ available: number; pending: number; currency: string }> {
    throw new Error("Not implemented");
  }

  categorizeTransaction(event: PaymentEvent): string {
    throw new Error("Not implemented");
  }
}

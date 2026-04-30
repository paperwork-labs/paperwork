export type BillStatus = "pending" | "approved" | "paid" | "rejected";

export type Bill = {
  id: string;
  vendor_id: string;
  status: BillStatus;
  due_date: string;
  amount_usd: number;
  description: string;
  attachments: string[];
  created_at: string;
  updated_at: string;
};

export type BillsListPage = {
  items: Bill[];
  total: number;
};

export const BILL_STATUS_LABELS: Record<BillStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  paid: "Paid",
  rejected: "Rejected",
};

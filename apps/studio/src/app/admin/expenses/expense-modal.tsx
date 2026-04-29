"use client";

import { useState, useRef } from "react";
import { X, Upload, Loader2, AlertCircle } from "lucide-react";
import type { Expense, ExpenseCategory, ExpenseSource } from "@/types/expenses";
import { CATEGORY_LABELS } from "@/types/expenses";

const CATEGORIES = Object.entries(CATEGORY_LABELS) as [ExpenseCategory, string][];

const ALLOWED_MIME = ["image/png", "image/jpeg", "image/webp", "application/pdf"];
const MAX_SIZE_BYTES = 10 * 1024 * 1024;

type Props = {
  onClose: () => void;
  onSuccess: (expense: Expense) => void;
};

export function SubmitExpenseModal({ onClose, onSuccess }: Props) {
  const [vendor, setVendor] = useState("");
  const [amountDollars, setAmountDollars] = useState("");
  const [currency] = useState("USD");
  const [category, setCategory] = useState<ExpenseCategory>("misc");
  const [source] = useState<ExpenseSource>("manual");
  const [occurredAt, setOccurredAt] = useState(
    new Date().toISOString().slice(0, 10)
  );
  const [notes, setNotes] = useState("");
  const [receipt, setReceipt] = useState<File | null>(null);
  const [receiptError, setReceiptError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function handleFile(file: File | null) {
    if (!file) {
      setReceipt(null);
      return;
    }
    if (!ALLOWED_MIME.includes(file.type)) {
      setReceiptError("Allowed types: PNG, JPEG, WebP, PDF");
      return;
    }
    if (file.size > MAX_SIZE_BYTES) {
      setReceiptError("File too large (max 10 MB)");
      return;
    }
    setReceiptError(null);
    setReceipt(file);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const amountCents = Math.round(parseFloat(amountDollars) * 100);
    if (!vendor.trim()) return setError("Vendor is required");
    if (isNaN(amountCents) || amountCents < 0) return setError("Enter a valid amount");

    const payload = {
      vendor: vendor.trim(),
      amount_cents: amountCents,
      currency,
      category,
      source,
      occurred_at: occurredAt,
      notes: notes.trim(),
      tags: [],
    };

    const formData = new FormData();
    formData.append("body", JSON.stringify(payload));
    if (receipt) formData.append("receipt", receipt);

    setSubmitting(true);
    try {
      const res = await fetch("/api/admin/expenses", {
        method: "POST",
        body: formData,
      });
      const json = await res.json();
      if (!res.ok || !json.success) {
        throw new Error(json.error || "Failed to submit expense");
      }
      onSuccess(json.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="submit-expense-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
    >
      <div className="w-full max-w-lg rounded-2xl border border-zinc-800 bg-zinc-950 shadow-2xl">
        <div className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
          <h2 id="submit-expense-title" className="text-base font-semibold text-zinc-100">
            Submit expense
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 p-6">
          {error ? (
            <div className="flex items-center gap-2 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          ) : null}

          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="mb-1.5 block text-xs font-medium text-zinc-400">
                Vendor / merchant
              </label>
              <input
                type="text"
                value={vendor}
                onChange={(e) => setVendor(e.target.value)}
                placeholder="e.g. Hetzner, OpenAI"
                required
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 focus:border-zinc-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-medium text-zinc-400">
                Amount (USD)
              </label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={amountDollars}
                onChange={(e) => setAmountDollars(e.target.value)}
                placeholder="0.00"
                required
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 focus:border-zinc-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-medium text-zinc-400">Date</label>
              <input
                type="date"
                value={occurredAt}
                onChange={(e) => setOccurredAt(e.target.value)}
                required
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:border-zinc-500 focus:outline-none"
              />
            </div>

            <div className="col-span-2">
              <label className="mb-1.5 block text-xs font-medium text-zinc-400">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value as ExpenseCategory)}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:border-zinc-500 focus:outline-none"
              >
                {CATEGORIES.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>

            <div className="col-span-2">
              <label className="mb-1.5 block text-xs font-medium text-zinc-400">
                Notes (optional)
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={2}
                placeholder="What is this for?"
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 focus:border-zinc-500 focus:outline-none"
              />
            </div>

            <div className="col-span-2">
              <label className="mb-1.5 block text-xs font-medium text-zinc-400">
                Receipt (optional)
              </label>
              <div
                role="button"
                tabIndex={0}
                onClick={() => fileRef.current?.click()}
                onKeyDown={(e) => e.key === "Enter" && fileRef.current?.click()}
                className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-zinc-700 bg-zinc-900/50 px-4 py-6 text-center transition hover:border-zinc-500"
              >
                <Upload className="h-5 w-5 text-zinc-500" />
                {receipt ? (
                  <p className="text-sm text-zinc-300">{receipt.name}</p>
                ) : (
                  <p className="text-sm text-zinc-500">
                    PNG, JPEG, WebP, or PDF — max 10 MB
                  </p>
                )}
                <input
                  ref={fileRef}
                  type="file"
                  accept={ALLOWED_MIME.join(",")}
                  onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
                  className="sr-only"
                />
              </div>
              {receiptError ? (
                <p className="mt-1 text-xs text-red-400">{receiptError}</p>
              ) : null}
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex items-center gap-2 rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-900 transition hover:bg-white disabled:opacity-50"
            >
              {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
              Submit expense
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

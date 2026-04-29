"use client";

import { useCallback, useRef, useState } from "react";
import { Upload, X, Plus } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@paperwork-labs/ui";
import { Button } from "@paperwork-labs/ui";
import { Input } from "@paperwork-labs/ui";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@paperwork-labs/ui";

const CATEGORIES = [
  { value: "infra", label: "Infrastructure" },
  { value: "ai", label: "AI / ML" },
  { value: "contractors", label: "Contractors" },
  { value: "tools", label: "Tools" },
  { value: "legal", label: "Legal" },
  { value: "tax", label: "Tax" },
  { value: "domains", label: "Domains" },
  { value: "ops", label: "Operations" },
  { value: "misc", label: "Misc" },
] as const;

type Props = {
  onCreated?: () => void;
};

export function SubmitExpenseModal({ onCreated }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const [vendor, setVendor] = useState("");
  const [amountStr, setAmountStr] = useState("");
  const [category, setCategory] = useState<string>("");
  const [notes, setNotes] = useState("");
  const [tags, setTags] = useState("");

  const handleFile = useCallback((file: File) => {
    setReceipt(file);
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      const amountCents = Math.round(parseFloat(amountStr) * 100);
      if (!vendor.trim() || !category || isNaN(amountCents) || amountCents <= 0) {
        setError("Vendor, amount, and category are required.");
        return;
      }

      setLoading(true);
      const form = new FormData();
      form.set("vendor", vendor.trim());
      form.set("amount_cents", String(amountCents));
      form.set("category", category);
      form.set("notes", notes.trim());
      form.set("tags", tags.trim());
      form.set("submitted_by", "founder");
      if (receipt) form.set("receipt", receipt);

      try {
        const res = await fetch("/api/admin/expenses", {
          method: "POST",
          body: form,
        });
        if (!res.ok) {
          const text = await res.text();
          setError(`Failed: ${res.status} — ${text.slice(0, 200)}`);
          setLoading(false);
          return;
        }
        setOpen(false);
        setVendor("");
        setAmountStr("");
        setCategory("");
        setNotes("");
        setTags("");
        setReceipt(null);
        onCreated?.();
      } catch (err) {
        setError(String(err));
      } finally {
        setLoading(false);
      }
    },
    [vendor, amountStr, category, notes, tags, receipt, onCreated],
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          size="sm"
          className="gap-1.5 bg-zinc-700 text-zinc-100 hover:bg-zinc-600"
          aria-label="Submit new expense"
        >
          <Plus className="h-3.5 w-3.5" />
          Submit expense
        </Button>
      </DialogTrigger>
      <DialogContent className="border-zinc-800 bg-zinc-900 text-zinc-100 sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-zinc-100">Submit expense</DialogTitle>
        </DialogHeader>
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="expense-vendor" className="block text-xs font-medium text-zinc-400">
              Vendor <span aria-hidden>*</span>
            </label>
            <Input
              id="expense-vendor"
              value={vendor}
              onChange={(e) => setVendor(e.target.value)}
              placeholder="e.g. Hetzner, OpenAI, Namecheap"
              required
              className="border-zinc-700 bg-zinc-800 text-zinc-100 placeholder:text-zinc-600"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label htmlFor="expense-amount" className="block text-xs font-medium text-zinc-400">
                Amount (USD) <span aria-hidden>*</span>
              </label>
              <Input
                id="expense-amount"
                type="number"
                step="0.01"
                min="0.01"
                value={amountStr}
                onChange={(e) => setAmountStr(e.target.value)}
                placeholder="0.00"
                required
                className="border-zinc-700 bg-zinc-800 text-zinc-100 placeholder:text-zinc-600"
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="expense-category" className="block text-xs font-medium text-zinc-400">
                Category <span aria-hidden>*</span>
              </label>
              <Select value={category} onValueChange={setCategory} required>
                <SelectTrigger
                  id="expense-category"
                  className="border-zinc-700 bg-zinc-800 text-zinc-100"
                  aria-label="Select category"
                >
                  <SelectValue placeholder="Pick one" />
                </SelectTrigger>
                <SelectContent className="border-zinc-700 bg-zinc-900">
                  {CATEGORIES.map((c) => (
                    <SelectItem key={c.value} value={c.value} className="text-zinc-200 focus:bg-zinc-800">
                      {c.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="expense-notes" className="block text-xs font-medium text-zinc-400">
              Notes
            </label>
            <Input
              id="expense-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional description"
              className="border-zinc-700 bg-zinc-800 text-zinc-100 placeholder:text-zinc-600"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="expense-tags" className="block text-xs font-medium text-zinc-400">
              Tags <span className="text-zinc-600">(comma-separated)</span>
            </label>
            <Input
              id="expense-tags"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="e.g. q2, hosting, one-time"
              className="border-zinc-700 bg-zinc-800 text-zinc-100 placeholder:text-zinc-600"
            />
          </div>

          {/* DropZone for receipt */}
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-zinc-400">Receipt (optional)</p>
            <div
              role="button"
              tabIndex={0}
              aria-label="Drop zone for receipt file"
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => fileRef.current?.click()}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") fileRef.current?.click(); }}
              className={`flex min-h-[80px] cursor-pointer items-center justify-center rounded-lg border-2 border-dashed transition-colors ${
                dragOver
                  ? "border-zinc-400 bg-zinc-800/60"
                  : "border-zinc-700 bg-zinc-800/30 hover:border-zinc-600"
              }`}
            >
              <input
                ref={fileRef}
                type="file"
                accept="image/*,application/pdf"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFile(file);
                }}
                aria-label="Upload receipt file"
              />
              {receipt ? (
                <div className="flex items-center gap-2 text-sm text-zinc-300">
                  <Upload className="h-4 w-4 text-zinc-400" />
                  <span className="max-w-[180px] truncate">{receipt.name}</span>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); setReceipt(null); }}
                    className="text-zinc-500 hover:text-zinc-200"
                    aria-label="Remove receipt"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-1 text-center">
                  <Upload className="h-5 w-5 text-zinc-500" />
                  <p className="text-xs text-zinc-500">Drop a PDF or image, or click to browse</p>
                </div>
              )}
            </div>
          </div>

          {error && (
            <p className="rounded-lg border border-red-500/30 bg-red-950/30 px-3 py-2 text-xs text-red-300" role="alert">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setOpen(false)}
              className="text-zinc-400 hover:text-zinc-200"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={loading}
              className="bg-zinc-700 text-zinc-100 hover:bg-zinc-600 disabled:opacity-50"
              aria-label="Submit expense form"
            >
              {loading ? "Submitting…" : "Submit expense"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

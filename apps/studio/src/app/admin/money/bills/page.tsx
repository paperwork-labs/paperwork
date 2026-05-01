import { Mail } from "lucide-react";

export const metadata = {
  title: "Bills | Paperwork Studio",
};

export default function BillsFromEmailPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-100">
          Bills
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Invoice detection and bill management from email
        </p>
      </div>

      <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-12 text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-zinc-800/60">
          <Mail className="h-6 w-6 text-zinc-400" />
        </div>
        <h2 className="text-lg font-semibold text-zinc-200">
          Bills from email coming soon
        </h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-zinc-500">
          Wave 1 Money MVP will automatically detect invoices in your inbox,
          extract key details, and help you track payments.
        </p>
      </div>
    </div>
  );
}

import { ExternalLink } from "lucide-react";
import { Card, CardContent } from "@paperwork-labs/ui";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type InfraVendorRow = {
  id: string;
  name: string;
  category: string;
  pricing_url: string;
  monthly_budget: number | null;
};

function categoryLabel(cat: string): string {
  return cat.replace(/_/g, " ");
}

async function fetchRegistryVendors(): Promise<InfraVendorRow[] | null> {
  const base = process.env.BRAIN_API_URL?.trim().replace(/\/+$/, "");
  if (!base) return null;

  try {
    const res = await fetch(`${base}/api/v1/infra/vendors`, { cache: "no-store" });
    if (!res.ok) return null;
    const body = (await res.json()) as {
      success?: boolean;
      data?: { vendors?: InfraVendorRow[] };
    };
    if (!body.success || !body.data?.vendors) return null;
    return body.data.vendors;
  } catch {
    return null;
  }
}

export default async function VendorsTab() {
  const vendors = await fetchRegistryVendors();
  const sorted =
    vendors?.slice().sort((a, b) => {
      const c = a.category.localeCompare(b.category);
      return c !== 0 ? c : a.name.localeCompare(b.name);
    }) ?? null;

  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-400">
        Vendor catalog from Brain <code className="text-zinc-500">infra_registry.json</code>{" "}
        (public GET <code className="text-zinc-500">/api/v1/infra/vendors</code>).
      </p>
      {!process.env.BRAIN_API_URL?.trim() ? (
        <div className="rounded-xl border border-[var(--status-warning)]/40 bg-[var(--status-warning-bg)] px-4 py-3 text-sm text-zinc-300">
          Set <code className="text-zinc-200">BRAIN_API_URL</code> on Studio to load vendors from Brain.
        </div>
      ) : null}
      {sorted && sorted.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {sorted.map((v) => (
            <Card key={v.id} className="border-zinc-800">
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-zinc-100">{v.name}</p>
                    <p className="mt-0.5 text-xs capitalize text-zinc-500">{categoryLabel(v.category)}</p>
                  </div>
                  {v.monthly_budget !== null ? (
                    <span className="shrink-0 rounded border border-zinc-700 px-2 py-0.5 font-mono text-xs text-zinc-400">
                      ${v.monthly_budget}/mo
                    </span>
                  ) : (
                    <span className="shrink-0 text-xs text-zinc-600">—</span>
                  )}
                </div>
                <a
                  href={v.pricing_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-3 inline-flex items-center gap-1 text-xs text-zinc-500 transition hover:text-zinc-300"
                >
                  Pricing <ExternalLink className="h-3 w-3" />
                </a>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-zinc-700 bg-zinc-900/40 px-4 py-8 text-center text-sm text-zinc-500">
          {sorted === null
            ? "Could not reach Brain or vendors payload was empty."
            : "No vendors in registry."}
        </div>
      )}
    </div>
  );
}

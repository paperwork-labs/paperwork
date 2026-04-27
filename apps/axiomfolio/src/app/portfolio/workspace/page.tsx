import { redirect } from "next/navigation";

type SearchParamValue = string | string[] | undefined;

/**
 * Legacy Vite URL: same feature lives at `/market/workspace` (see
 * `apps/axiomfolio/src/App.tsx` `PreserveRedirect`). Query string is preserved;
 * `hash` is not (not available to the server; client-only navigations to
 * `/market/workspace` keep hash in the client).
 */
function searchParamsToQueryString(
  sp: Readonly<Record<string, SearchParamValue>>,
): string {
  const u = new URLSearchParams();
  for (const [key, value] of Object.entries(sp)) {
    if (value === undefined) continue;
    if (Array.isArray(value)) {
      for (const item of value) u.append(key, item);
    } else {
      u.set(key, value);
    }
  }
  return u.toString();
}

export default async function PortfolioWorkspacePage({
  searchParams,
}: {
  searchParams: Promise<Readonly<Record<string, SearchParamValue>>>;
}) {
  const sp = await searchParams;
  const qs = searchParamsToQueryString(sp);
  redirect(`/market/workspace${qs ? `?${qs}` : ""}`);
}

import { redirect } from "next/navigation";

/** Legacy Vite path `/market/scanner` — same destination as `/scanner`. */
export default function MarketScannerRedirectPage() {
  redirect("/market/tracked?mode=scan");
}

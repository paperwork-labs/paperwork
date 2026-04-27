import Link from "next/link";
import { RequireAuthClient } from "@/components/auth/RequireAuthClient";

export default function LabPage() {
  return (
    <RequireAuthClient>
      <div className="p-6">
        <h1 className="text-2xl font-semibold tracking-tight">Lab</h1>
        <p className="text-muted-foreground mt-2">Backtesting and research tools.</p>
        <ul className="mt-4 list-inside list-disc text-sm text-muted-foreground">
          <li>
            <Link className="text-foreground hover:underline" href="/lab/monte-carlo">
              Monte Carlo simulator
            </Link>
          </li>
          <li>
            <Link className="text-foreground hover:underline" href="/lab/walk-forward">
              Walk-forward optimizer
            </Link>
          </li>
        </ul>
      </div>
    </RequireAuthClient>
  );
}

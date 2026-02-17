import { useMemo } from "react";
import { useAuthOptional } from "../context/AuthContext";

export type TableDensity = "comfortable" | "compact";

export function useUserPreferences(): {
  currency: string;
  timezone: string;
  tableDensity: TableDensity;
  coverageHistogramWindowDays: number | null;
} {
  const auth = useAuthOptional();
  const user = auth?.user ?? null;

  return useMemo(() => {
    const currency = (user?.currency_preference || "USD").toUpperCase();
    const timezone = user?.timezone || "America/Los_Angeles";
    const td = user?.ui_preferences?.table_density;
    const tableDensity: TableDensity = td === "compact" ? "compact" : "comfortable";
    const raw = Number(user?.ui_preferences?.coverage_histogram_window_days);
    const coverageHistogramWindowDays =
      Number.isFinite(raw) && raw > 0 ? raw : null;
    return { currency, timezone, tableDensity, coverageHistogramWindowDays };
  }, [
    user?.currency_preference,
    user?.timezone,
    user?.ui_preferences?.table_density,
    user?.ui_preferences?.coverage_histogram_window_days,
  ]);
}



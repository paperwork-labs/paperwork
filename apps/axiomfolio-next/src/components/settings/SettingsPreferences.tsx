"use client";

import React from "react";
import toast from "react-hot-toast";
import { PageHeader } from "@/components/ui/Page";
import { authApi, handleApiError } from "@/services/api";
import { useAuth } from "@/context/AuthContext";
import { useColorMode } from "@/theme/colorMode";
import { IANA_TIMEZONES } from "@/constants/timezones";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const selectClass =
  "h-9 w-full max-w-[280px] rounded-md border border-input bg-background px-2.5 text-xs text-foreground shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30";

type SaveStatus = "idle" | "saving" | "saved" | "error";

export default function SettingsPreferences() {
  const { user, refreshMe } = useAuth();
  const { colorModePreference, setColorModePreference } = useColorMode();

  const [themePref, setThemePref] = React.useState<"system" | "light" | "dark">("system");
  const [tableDensity, setTableDensity] = React.useState<"comfortable" | "compact">("comfortable");
  const [timezone, setTimezone] = React.useState<string>(user?.timezone || "America/Los_Angeles");
  const [currency, setCurrency] = React.useState<string>((user?.currency_preference || "USD").toUpperCase());
  const [saveStatus, setSaveStatus] = React.useState<SaveStatus>("idle");
  const [debouncePending, setDebouncePending] = React.useState(false);
  const saveTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const debounceRef = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const mountedRef = React.useRef(true);

  React.useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const timezones = React.useMemo<ReadonlyArray<string>>(() => {
    try {
      const runtime = (Intl as unknown as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf?.(
        "timeZone",
      );
      if (Array.isArray(runtime) && runtime.length) return runtime;
    } catch {
      // Intl.supportedValuesOf unavailable (older browser); fall through to bundled list.
    }
    return IANA_TIMEZONES;
  }, []);

  React.useEffect(() => {
    const pref = user?.ui_preferences?.color_mode_preference;
    if (pref === "system" || pref === "light" || pref === "dark") {
      setThemePref(pref);
    } else {
      setThemePref(colorModePreference);
    }
    const td = user?.ui_preferences?.table_density;
    if (td === "comfortable" || td === "compact") setTableDensity(td);
    setTimezone(user?.timezone || "America/Los_Angeles");
    setCurrency((user?.currency_preference || "USD").toUpperCase());
  }, [
    user?.timezone,
    user?.currency_preference,
    user?.ui_preferences?.color_mode_preference,
    user?.ui_preferences?.table_density,
    colorModePreference,
  ]);

  const persist = React.useCallback(
    async (patch: {
      timezone?: string;
      currency_preference?: string;
      ui_preferences?: { color_mode_preference?: string; table_density?: string };
    }) => {
      if (!mountedRef.current) return;
      setSaveStatus("saving");
      clearTimeout(saveTimeoutRef.current);
      try {
        await authApi.updateMe(patch);
        if (patch.ui_preferences?.color_mode_preference) {
          setColorModePreference(patch.ui_preferences.color_mode_preference as "system" | "light" | "dark");
        }
        await refreshMe();
        if (!mountedRef.current) return;
        setSaveStatus("saved");
        saveTimeoutRef.current = setTimeout(() => {
          if (mountedRef.current) setSaveStatus("idle");
        }, 2000);
      } catch (e) {
        if (!mountedRef.current) return;
        setSaveStatus("error");
        toast.error(handleApiError(e));
        saveTimeoutRef.current = setTimeout(() => {
          if (mountedRef.current) setSaveStatus("idle");
        }, 3000);
      }
    },
    [refreshMe, setColorModePreference],
  );

  const handleThemeChange = (next: "system" | "light" | "dark") => {
    setThemePref(next);
    setColorModePreference(next);
    void persist({ ui_preferences: { color_mode_preference: next, table_density: tableDensity } });
  };

  const handleDensityChange = (next: "comfortable" | "compact") => {
    setTableDensity(next);
    void persist({ ui_preferences: { color_mode_preference: themePref, table_density: next } });
  };

  const handleTimezoneChange = (next: string) => {
    setTimezone(next);
    void persist({ timezone: next });
  };

  const handleCurrencyChange = (raw: string) => {
    const next = raw.toUpperCase();
    setCurrency(next);
    clearTimeout(debounceRef.current);
    if (next.length === 3) {
      setDebouncePending(true);
      debounceRef.current = setTimeout(() => {
        setDebouncePending(false);
        void persist({ currency_preference: next });
      }, 600);
    } else {
      setDebouncePending(false);
    }
  };

  const statusBadge =
    saveStatus === "saving" ? (
      <Badge variant="secondary" className="shrink-0 font-normal">
        Saving…
      </Badge>
    ) : saveStatus === "saved" ? (
      <Badge
        variant="outline"
        className="shrink-0 border-emerald-500/40 bg-emerald-500/10 font-normal text-emerald-800 dark:text-emerald-200"
      >
        Saved
      </Badge>
    ) : saveStatus === "error" ? (
      <Badge variant="destructive" className="shrink-0 font-normal">
        Error
      </Badge>
    ) : debouncePending ? (
      <Badge variant="secondary" className="shrink-0 font-normal text-muted-foreground">
        Pending…
      </Badge>
    ) : null;

  return (
    <div className="w-full">
      <div className="mx-auto w-full max-w-[960px]">
        <div className="mb-0 flex items-center justify-between gap-3">
          <PageHeader title="Preferences" subtitle="Changes are saved automatically." />
          {statusBadge}
        </div>
        <div className="mt-4 flex flex-col gap-4">
          <Card>
            <CardContent className="space-y-4 pt-6">
              <h2 className="font-heading font-semibold text-foreground">Appearance</h2>
              <div>
                <Label htmlFor="pref-theme" className="mb-2 block text-muted-foreground">
                  Theme
                </Label>
                <select
                  id="pref-theme"
                  className={selectClass}
                  value={themePref}
                  onChange={(e) => handleThemeChange(e.target.value as "system" | "light" | "dark")}
                >
                  <option value="system">Use system preference</option>
                  <option value="light">Light</option>
                  <option value="dark">Dark</option>
                </select>
              </div>
              <div>
                <Label htmlFor="pref-density" className="mb-2 block text-muted-foreground">
                  Table density
                </Label>
                <select
                  id="pref-density"
                  className={selectClass}
                  value={tableDensity}
                  onChange={(e) => handleDensityChange(e.target.value as "comfortable" | "compact")}
                >
                  <option value="comfortable">Comfortable</option>
                  <option value="compact">Compact</option>
                </select>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="space-y-4 pt-6">
              <h2 className="font-heading font-semibold text-foreground">Locale</h2>
              <div className="flex flex-wrap gap-4">
                <div className="min-w-0 flex-1 basis-full md:min-w-[320px]">
                  <Label htmlFor="pref-tz" className="mb-1.5 block text-muted-foreground">
                    Timezone
                  </Label>
                  <select
                    id="pref-tz"
                    className={cn(selectClass, "max-w-none md:max-w-full")}
                    value={timezone}
                    onChange={(e) => handleTimezoneChange(e.target.value)}
                  >
                    {timezones.map((tz) => (
                      <option key={tz} value={tz}>
                        {tz}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="min-w-0 basis-full md:max-w-[200px]">
                  <Label htmlFor="pref-currency" className="mb-1.5 block text-muted-foreground">
                    Currency
                  </Label>
                  <Input
                    id="pref-currency"
                    value={currency}
                    onChange={(e) => handleCurrencyChange(e.target.value)}
                    placeholder="USD"
                    maxLength={3}
                    className="max-w-[200px]"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">3-letter code (e.g. USD, EUR, GBP)</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

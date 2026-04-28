import * as React from "react";
import { LayoutDashboard, LineChart, Settings, Shield } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

export type MockDashboardChrome = "default" | "admin";

export type MockDashboardLayoutProps = {
  /** When true, sidebar uses narrow width (icon rail). */
  collapsed: boolean;
  /** Visual variant for design QA (header + labels). */
  chrome?: MockDashboardChrome;
};

/**
 * Lightweight dashboard shell for Storybook — sidebar, header, and outlet only.
 * No AxiomFolio imports; Tailwind + react-router only.
 */
export function MockDashboardLayout({ collapsed, chrome = "default" }: MockDashboardLayoutProps) {
  const navLinkClass = React.useCallback(
    ({ isActive }: { isActive: boolean }) =>
      [
        "flex items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors",
        collapsed ? "justify-center px-0" : "",
        isActive
          ? "bg-muted font-medium text-foreground"
          : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
      ]
        .filter(Boolean)
        .join(" "),
    [collapsed]
  );

  return (
    <div className="flex min-h-[100vh] w-full min-w-0 bg-background text-foreground">
      <aside
        className={[
          "flex shrink-0 flex-col border-r border-border bg-card py-3 transition-[width] duration-200",
          collapsed ? "w-14" : "w-56",
        ].join(" ")}
        aria-label="Sidebar (mock)"
      >
        <div className={["mb-4 px-3", collapsed ? "px-2" : ""].join(" ")}>
          <div
            className={[
              "rounded-md border border-border bg-muted/40 font-semibold tracking-tight",
              collapsed ? "mx-auto flex h-9 w-9 items-center justify-center text-xs" : "px-3 py-2 text-sm",
            ].join(" ")}
          >
            {collapsed ? "P" : "Paperwork"}
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-0.5 px-2">
          <NavLink to="/" end className={navLinkClass} title="Dashboard">
            <LayoutDashboard className="h-4 w-4 shrink-0" />
            {!collapsed ? <span>Dashboard</span> : null}
          </NavLink>
          <NavLink to="/market/coverage" className={navLinkClass} title="Coverage">
            <LineChart className="h-4 w-4 shrink-0" />
            {!collapsed ? <span>Market / Coverage</span> : null}
          </NavLink>
          <NavLink to="/settings/admin/system" className={navLinkClass} title="Admin">
            <Settings className="h-4 w-4 shrink-0" />
            {!collapsed ? <span>Settings</span> : null}
          </NavLink>
        </nav>
        <div className="mt-auto border-t border-border px-2 pt-2">
          <div
            className={[
              "rounded-md bg-muted/50 text-xs text-muted-foreground",
              collapsed ? "p-1 text-center" : "px-2 py-1.5",
            ].join(" ")}
          >
            {collapsed ? "v" : "Mock shell"}
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-card px-4">
          <div className="flex min-w-0 items-center gap-2">
            <span className="truncate text-sm font-medium text-foreground">Design QA</span>
            {chrome === "admin" ? (
              <span className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/60 px-2 py-0.5 text-xs font-medium text-foreground">
                <Shield className="h-3 w-3" aria-hidden />
                Admin
              </span>
            ) : null}
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {chrome === "admin" ? (
              <span className="hidden sm:inline">IBKR_MAIN · SCHWAB</span>
            ) : (
              <span className="hidden sm:inline">Unauthenticated</span>
            )}
            <span className="rounded-md border border-border px-2 py-1 font-mono text-[10px] uppercase tracking-wide">
              {collapsed ? "Collapsed" : "Expanded"}
            </span>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-auto bg-background">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

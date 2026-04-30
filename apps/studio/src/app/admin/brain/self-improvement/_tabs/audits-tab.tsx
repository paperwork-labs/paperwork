"use client";

import { useState, useEffect, useCallback } from "react";
import { AlertCircle, CheckCircle2, RefreshCw, Clock, TriangleAlert } from "lucide-react";

type AuditCadence = "weekly" | "monthly" | "quarterly";
type Severity = "info" | "warn" | "error";

type AuditFinding = {
  audit_id: string;
  severity: Severity;
  title: string;
  detail: string;
  file_path: string | null;
  line: number | null;
};

type AuditRun = {
  audit_id: string;
  ran_at: string;
  findings: AuditFinding[];
  summary: string;
  next_cadence: AuditCadence;
};

type AuditRow = {
  id: string;
  name: string;
  cadence: AuditCadence;
  runner_module: string;
  pillar: string;
  enabled: boolean;
  last_run: AuditRun | null;
};

const CADENCES: AuditCadence[] = ["weekly", "monthly", "quarterly"];

function CadenceBadge({ cadence }: { cadence: AuditCadence }) {
  const colors: Record<AuditCadence, string> = {
    weekly: "bg-blue-500/20 text-blue-300 border-blue-500/30",
    monthly: "bg-violet-500/20 text-violet-300 border-violet-500/30",
    quarterly: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${colors[cadence]}`}
    >
      {cadence}
    </span>
  );
}

function SeverityIcon({ severity }: { severity: Severity }) {
  if (severity === "error")
    return <AlertCircle className="h-3.5 w-3.5 text-rose-400" />;
  if (severity === "warn")
    return <TriangleAlert className="h-3.5 w-3.5 text-amber-400" />;
  return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />;
}

function FindingCount({ run }: { run: AuditRun | null }) {
  if (!run) return <span className="text-xs text-zinc-500">Never run</span>;
  const errors = run.findings.filter((f) => f.severity === "error").length;
  const warns = run.findings.filter((f) => f.severity === "warn").length;
  const infos = run.findings.filter((f) => f.severity === "info").length;
  return (
    <div className="flex items-center gap-1.5 text-xs">
      {errors > 0 && (
        <span className="flex items-center gap-0.5 text-rose-400">
          <SeverityIcon severity="error" />
          {errors}
        </span>
      )}
      {warns > 0 && (
        <span className="flex items-center gap-0.5 text-amber-400">
          <SeverityIcon severity="warn" />
          {warns}
        </span>
      )}
      {infos > 0 && (
        <span className="flex items-center gap-0.5 text-emerald-400">
          <SeverityIcon severity="info" />
          {infos}
        </span>
      )}
      {run.findings.length === 0 && (
        <span className="text-zinc-500">0 findings</span>
      )}
    </div>
  );
}

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

/** F-042/F-043 — Brain audit admin via same-origin proxy; no client Brain secret. */
export function AuditsTab() {
  const [audits, setAudits] = useState<AuditRow[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [brainUnavailable, setBrainUnavailable] = useState(false);
  const [cadenceFilter, setCadenceFilter] = useState<AuditCadence | "all">("all");
  const [runningId, setRunningId] = useState<string | null>(null);
  const [overrideId, setOverrideId] = useState<string | null>(null);

  const loadAudits = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setBrainUnavailable(false);
      const res = await fetch("/api/admin/brain/audits", { cache: "no-store" });
      if (res.status === 503) {
        setBrainUnavailable(true);
        setAudits(null);
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = (await res.json()) as { success: boolean; data: AuditRow[] };
      setAudits(body.data ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audits");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAudits();
  }, [loadAudits]);

  const triggerRun = async (auditId: string) => {
    if (runningId) return;
    setRunningId(auditId);
    try {
      const res = await fetch(`/api/admin/brain/audits/${encodeURIComponent(auditId)}/run`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await loadAudits();
    } catch (err) {
      console.error("run audit failed:", err);
    } finally {
      setRunningId(null);
    }
  };

  const overrideCadence = async (auditId: string, cadence: AuditCadence) => {
    setOverrideId(auditId);
    try {
      const res = await fetch(`/api/admin/brain/audits/${encodeURIComponent(auditId)}/cadence`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cadence }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await loadAudits();
    } catch (err) {
      console.error("override cadence failed:", err);
    } finally {
      setOverrideId(null);
    }
  };

  const filtered = audits
    ? cadenceFilter === "all"
      ? audits
      : audits.filter((a) => a.cadence === cadenceFilter)
    : [];

  if (brainUnavailable) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100/90">
        <AlertCircle className="h-4 w-4 shrink-0" />
        <p>
          Brain admin proxy is not configured. Set <code className="rounded bg-zinc-800 px-1">BRAIN_API_URL</code>{" "}
          and <code className="rounded bg-zinc-800 px-1">BRAIN_API_SECRET</code> on the Studio server (not in the
          browser).
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Cadence filter chips */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-zinc-500">Filter:</span>
        {(["all", ...CADENCES] as const).map((c) => (
          <button
            key={c}
            onClick={() => setCadenceFilter(c)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
              cadenceFilter === c
                ? "border-zinc-400 bg-zinc-700 text-zinc-100"
                : "border-zinc-700 bg-transparent text-zinc-400 hover:border-zinc-500 hover:text-zinc-200"
            }`}
          >
            {c}
          </button>
        ))}
        <button
          onClick={() => void loadAudits()}
          className="ml-auto flex items-center gap-1 rounded border border-zinc-700 px-2 py-1 text-xs text-zinc-400 hover:border-zinc-500 hover:text-zinc-200"
        >
          <RefreshCw className="h-3 w-3" />
          Refresh
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100/90">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p>Failed to load audits: {error}</p>
        </div>
      )}

      {loading && !audits && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-14 animate-pulse rounded-lg bg-zinc-800" />
          ))}
        </div>
      )}

      {filtered.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-zinc-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-900">
                <th className="px-4 py-2 text-left text-xs font-medium text-zinc-500">Audit</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-zinc-500">Cadence</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-zinc-500">Last run</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-zinc-500">Findings</th>
                <th className="px-4 py-2 text-right text-xs font-medium text-zinc-500">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((audit, idx) => (
                <tr
                  key={audit.id}
                  className={`border-b border-zinc-800/60 ${idx % 2 === 0 ? "bg-zinc-900/50" : "bg-zinc-900/20"}`}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-zinc-200">{audit.name}</div>
                    <div className="text-xs text-zinc-500">{audit.pillar}</div>
                  </td>
                  <td className="px-4 py-3">
                    <CadenceBadge cadence={audit.cadence} />
                  </td>
                  <td className="px-4 py-3">
                    {audit.last_run ? (
                      <span className="flex items-center gap-1 text-xs text-zinc-400">
                        <Clock className="h-3 w-3" />
                        {formatRelative(audit.last_run.ran_at)}
                      </span>
                    ) : (
                      <span className="text-xs text-zinc-600">Never</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <FindingCount run={audit.last_run} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      {/* Cadence override dropdown */}
                      <select
                        value={audit.cadence}
                        disabled={overrideId === audit.id}
                        onChange={(e) =>
                          void overrideCadence(audit.id, e.target.value as AuditCadence)
                        }
                        className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs text-zinc-300 disabled:opacity-50"
                        aria-label={`Override cadence for ${audit.name}`}
                      >
                        {CADENCES.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                      {/* Run now button */}
                      <button
                        onClick={() => void triggerRun(audit.id)}
                        disabled={runningId !== null}
                        className="flex items-center gap-1 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs text-zinc-300 hover:border-zinc-500 hover:text-zinc-100 disabled:opacity-50"
                        aria-label={`Run ${audit.name} now`}
                      >
                        {runningId === audit.id ? (
                          <RefreshCw className="h-3 w-3 animate-spin" />
                        ) : (
                          <RefreshCw className="h-3 w-3" />
                        )}
                        Run now
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {audits && filtered.length === 0 && !loading && (
        <p className="text-center text-sm text-zinc-500">No audits match the selected filter.</p>
      )}
    </div>
  );
}

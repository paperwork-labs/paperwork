"use client";

import { useMemo, useState } from "react";

import {
  OPERATING_SCORE_PILLAR_ORDER,
  operatingScorePillarLabel,
} from "@/lib/operating-score-pillars";
import type { OperatingScoreEntry, Pillar } from "@/types/operating-score";

type SortKey = "pillar" | "weight" | "score" | "measured" | "trend";

function scoreToneClass(score: number): string {
  if (score < 70) return "text-rose-400";
  if (score < 90) return "text-amber-400";
  return "text-emerald-400";
}

function trendForPillar(
  history: OperatingScoreEntry[],
  pillarId: string,
): "up" | "down" | "flat" | null {
  if (history.length < 2) return null;
  const prev = history[history.length - 2]?.pillars[pillarId];
  const curr = history[history.length - 1]?.pillars[pillarId];
  if (prev == null || curr == null) return null;
  const d = curr.score - prev.score;
  if (d > 0.001) return "up";
  if (d < -0.001) return "down";
  return "flat";
}

function trendGlyph(t: "up" | "down" | "flat" | null): string {
  if (t === "up") return "↑";
  if (t === "down") return "↓";
  if (t === "flat") return "→";
  return "—";
}

function trendSortValue(
  history: OperatingScoreEntry[],
  pillarId: string,
): number {
  if (history.length < 2) return 0;
  const prev = history[history.length - 2]?.pillars[pillarId];
  const curr = history[history.length - 1]?.pillars[pillarId];
  if (prev == null || curr == null) return 0;
  return curr.score - prev.score;
}

export function OperatingScorePillarTable({
  current,
  history,
}: {
  current: OperatingScoreEntry;
  history: OperatingScoreEntry[];
}) {
  const [sortKey, setSortKey] = useState<SortKey>("pillar");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const rows = useMemo(() => {
    return OPERATING_SCORE_PILLAR_ORDER.map((id) => {
      const p: Pillar | undefined = current.pillars[id];
      const label = operatingScorePillarLabel(id);
      const weight = p?.weight ?? 0;
      const score = p?.score ?? 0;
      const measured = p?.measured ?? false;
      const trend = trendForPillar(history, id);
      const trendDelta = trendSortValue(history, id);
      return { id, label, weight, score, measured, trend, trendDelta };
    });
  }, [current, history]);

  const sorted = useMemo(() => {
    const mult = sortDir === "asc" ? 1 : -1;
    const copy = [...rows];
    copy.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "pillar":
          cmp = a.label.localeCompare(b.label);
          break;
        case "weight":
          cmp = a.weight - b.weight;
          break;
        case "score":
          cmp = a.score - b.score;
          break;
        case "measured":
          cmp = Number(a.measured) - Number(b.measured);
          break;
        case "trend":
          cmp = a.trendDelta - b.trendDelta;
          break;
        default:
          cmp = 0;
      }
      return cmp * mult;
    });
    return copy;
  }, [rows, sortKey, sortDir]);

  function header(label: string, key: SortKey) {
    const active = sortKey === key;
    return (
      <button
        type="button"
        onClick={() => {
          if (active) {
            setSortDir((d) => (d === "asc" ? "desc" : "asc"));
          } else {
            setSortKey(key);
            setSortDir("asc");
          }
        }}
        className={`text-left text-xs font-medium uppercase tracking-wide ${
          active ? "text-zinc-200" : "text-zinc-500"
        } hover:text-zinc-300`}
      >
        {label}
        {active ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
      </button>
    );
  }

  return (
    <div className="mt-4 overflow-x-auto rounded-lg border border-zinc-800/80">
      <table
        className="w-full min-w-[480px] text-sm"
        aria-label="Operating score pillars"
        data-testid="operating-score-pillar-table"
      >
        <thead>
          <tr className="border-b border-zinc-800 bg-zinc-950/40">
            <th className="px-3 py-2">{header("Pillar", "pillar")}</th>
            <th className="px-3 py-2 text-right">{header("Weight", "weight")}</th>
            <th className="px-3 py-2 text-right">{header("Score", "score")}</th>
            <th className="px-3 py-2 text-center">{header("Measured", "measured")}</th>
            <th className="px-3 py-2 text-center">{header("Trend", "trend")}</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.id} className="border-b border-zinc-800/60 last:border-b-0">
              <td className="px-3 py-2 text-zinc-300">{row.label}</td>
              <td className="px-3 py-2 text-right tabular-nums text-zinc-400">{row.weight}%</td>
              <td
                className={`px-3 py-2 text-right tabular-nums font-medium ${scoreToneClass(row.score)}`}
              >
                {row.score.toFixed(1)}
              </td>
              <td className="px-3 py-2 text-center text-zinc-400">
                {row.measured ? "Y" : "N"}
              </td>
              <td className="px-3 py-2 text-center tabular-nums text-zinc-300">
                {trendGlyph(row.trend)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

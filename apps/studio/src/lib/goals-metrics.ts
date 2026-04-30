export type KeyResult = {
  id: string;
  title: string;
  target: number;
  current: number;
  unit: string;
  source_url: string | null;
};

export type Objective = {
  id: string;
  title: string;
  owner: string;
  key_results: KeyResult[];
};

export type GoalsJson = {
  quarter: string;
  objectives: Objective[];
};

/** Progress 0–100 from current/target (cap at 100). */
export function krProgressPct(kr: KeyResult): number {
  if (kr.target <= 0 || !Number.isFinite(kr.target)) return 0;
  return Math.min(100, (kr.current / kr.target) * 100);
}

export function objectiveProgressPct(obj: Objective): number {
  const krs = obj.key_results;
  if (krs.length === 0) return 0;
  const sum = krs.reduce((acc, kr) => acc + krProgressPct(kr), 0);
  return sum / krs.length;
}

export function collectKeyResults(objectives: Objective[]): KeyResult[] {
  return objectives.flatMap((o) => o.key_results);
}

export function computeGoalsRollup(objectives: Objective[]) {
  const krs = collectKeyResults(objectives);
  const onTrack = krs.filter((kr) => krProgressPct(kr) > 50).length;
  const atRisk = krs.filter((kr) => krProgressPct(kr) < 25).length;
  const overallPct =
    krs.length === 0
      ? 0
      : Math.round(krs.reduce((acc, kr) => acc + krProgressPct(kr), 0) / krs.length);
  return {
    objectiveCount: objectives.length,
    krOnTrack: onTrack,
    krAtRisk: atRisk,
    overallPct,
  };
}

/** Bar fill color: green >66%, amber 33–66%, red <33%. */
export function progressBarToneClass(pct: number): string {
  if (pct > 66) return "bg-[var(--status-success)]";
  if (pct >= 33) return "bg-[var(--status-warning)]";
  return "bg-[var(--status-danger)]";
}

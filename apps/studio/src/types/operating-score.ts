export type Pillar = {
  score: number;
  weight: number;
  weighted: number;
  measured: boolean;
  notes: string;
};

export type OperatingScoreGates = {
  l4_pass: boolean;
  l5_pass: boolean;
  lowest_pillar: string;
};

export type OperatingScoreEntry = {
  computed_at: string;
  total: number;
  pillars: Record<string, Pillar>;
  gates: OperatingScoreGates;
};

export type OperatingScoreResponse = {
  current: OperatingScoreEntry | null;
  history_last_12: OperatingScoreEntry[];
  gates: OperatingScoreGates;
};

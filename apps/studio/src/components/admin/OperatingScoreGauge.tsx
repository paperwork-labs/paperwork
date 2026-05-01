import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import { getBrainOperatingScoreHistoryEntries } from "@/lib/command-center";
import type { OperatingScoreResponse } from "@/types/operating-score";

import { OperatingScoreGaugeBody } from "./OperatingScoreGaugeBody";

function emptyOperatingResponse(): OperatingScoreResponse {
  return {
    current: null,
    history_last_12: [],
    gates: { l4_pass: false, l5_pass: false, lowest_pillar: "" },
  };
}

export async function OperatingScoreGauge() {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) {
    return (
      <OperatingScoreGaugeBody
        data={emptyOperatingResponse()}
        brainConfigured={false}
        operatingScoreHistory={null}
      />
    );
  }

  const [res, operatingScoreHistory] = await Promise.all([
    fetch(`${auth.root}/admin/operating-score`, {
      headers: { "X-Brain-Secret": auth.secret },
      cache: "no-store",
    }),
    getBrainOperatingScoreHistoryEntries(52),
  ]);

  if (!res.ok) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-6 ring-1 ring-rose-500/25">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-rose-300/90">
          Operating score
        </p>
        <p className="mt-2 text-sm text-rose-200">
          Could not load Operating Score from Brain (HTTP {res.status}).
        </p>
      </div>
    );
  }

  const json = (await res.json()) as {
    success?: boolean;
    data?: OperatingScoreResponse;
    error?: string;
  };

  if (json.success === false || json.data == null) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-6 ring-1 ring-rose-500/25">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-rose-300/90">
          Operating score
        </p>
        <p className="mt-2 text-sm text-rose-200">
          {json.error ?? "Brain returned an invalid Operating Score payload."}
        </p>
      </div>
    );
  }

  return (
    <OperatingScoreGaugeBody
      data={json.data}
      brainConfigured
      operatingScoreHistory={operatingScoreHistory}
    />
  );
}

import {
  getBrainLearningDecisions,
  getBrainLearningEpisodes,
  getBrainLearningSummary,
} from "@/lib/command-center";
import { BrainLearningClient } from "./learning-client";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type PageProps = {
  searchParams: Promise<{ persona?: string; product?: string }>;
};

function utcDayStartIso(d = new Date()): string {
  return new Date(
    Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), 0, 0, 0, 0),
  ).toISOString();
}

function utcYmd(d = new Date()): string {
  return d.toISOString().slice(0, 10);
}

export default async function BrainLearningPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const persona = params.persona?.trim() || undefined;
  const product = params.product?.trim() || undefined;

  const now = new Date();
  const sinceDay = utcDayStartIso(now);
  const since24h = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString();
  const anchorYmd = utcYmd(now);

  const [summary, episodes, decisions] = await Promise.all([
    getBrainLearningSummary(anchorYmd, { sparkDays: 14 }),
    getBrainLearningEpisodes({
      since: sinceDay,
      limit: 50,
      persona,
      product,
    }),
    getBrainLearningDecisions({ since: since24h, limit: 50 }),
  ]);

  const brainConfigured = Boolean(
    process.env.BRAIN_API_URL?.trim() && process.env.BRAIN_API_SECRET?.trim(),
  );

  const fetchFailed = brainConfigured && summary === null;

  return (
    <BrainLearningClient
      brainConfigured={brainConfigured}
      fetchFailed={fetchFailed}
      summary={summary}
      episodes={episodes}
      decisions={decisions}
      filterPersona={persona ?? null}
      filterProduct={product ?? null}
      fetchedAt={new Date().toISOString()}
    />
  );
}

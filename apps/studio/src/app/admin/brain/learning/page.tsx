import { LearningObservabilityClient } from "./learning-client";

export const dynamic = "force-dynamic";

export default function BrainLearningObservabilityPage() {
  const brainConfigured = Boolean(
    process.env.BRAIN_API_URL?.trim() && process.env.BRAIN_API_SECRET?.trim(),
  );
  return <LearningObservabilityClient brainConfigured={brainConfigured} />;
}

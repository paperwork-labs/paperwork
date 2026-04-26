import { getN8nMirrorSchedulerStatus } from "@/lib/command-center";
import N8nMirrorStatusClient from "@/components/admin/N8nMirrorStatusClient";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function N8nMirrorPage() {
  const initial = await getN8nMirrorSchedulerStatus();
  const initialCheckedAt = new Date().toISOString();
  return (
    <N8nMirrorStatusClient initialStatus={initial} initialCheckedAt={initialCheckedAt} />
  );
}

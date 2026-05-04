import { BrainTranscriptsList } from "@/components/admin/brain/BrainTranscriptsList";

export const dynamic = "force-dynamic";

export default function AdminTranscriptsPage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-8 md:px-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight text-zinc-50 md:text-3xl">
          Transcripts
        </h1>
        <p className="max-w-2xl text-sm text-zinc-500">
          Cursor agent transcripts ingested into Brain — grouped by session id.
        </p>
      </header>

      <BrainTranscriptsList />
    </div>
  );
}

import { Suspense } from "react";

import { Skeleton } from "@paperwork-labs/ui";

import { loadPersonasPageData } from "@/lib/personas";

import { PersonasTabsClient } from "./personas-tabs-client";

export const dynamic = "force-dynamic";

function PersonasFallback() {
  return (
    <div className="mx-auto w-full max-w-[1200px] px-4 py-8 md:px-6">
      <Skeleton className="mb-4 h-10 w-72 max-w-full" />
      <Skeleton className="h-12 w-full max-w-lg rounded-lg" />
      <Skeleton className="mt-6 h-[320px] w-full rounded-xl" />
    </div>
  );
}

export default async function BrainPersonasPage() {
  const data = await loadPersonasPageData();
  return (
    <Suspense fallback={<PersonasFallback />}>
      <PersonasTabsClient data={data} />
    </Suspense>
  );
}

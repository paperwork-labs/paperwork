import { notFound } from "next/navigation";

import { loadDocRaw } from "@/lib/docs";
import { DocEditClient } from "./doc-edit-client";

export const dynamic = "force-dynamic";

type Params = Promise<{ slug: string }>;

export default async function AdminDocEditPage({ params }: { params: Params }) {
  const { slug } = await params;
  const loaded = loadDocRaw(slug);
  if (!loaded) {
    notFound();
  }

  const githubTokenConfigured = Boolean(process.env.GITHUB_TOKEN?.trim());

  return (
    <DocEditClient
      slug={slug}
      initialRaw={loaded.raw}
      entry={loaded.entry}
      githubTokenConfigured={githubTokenConfigured}
    />
  );
}

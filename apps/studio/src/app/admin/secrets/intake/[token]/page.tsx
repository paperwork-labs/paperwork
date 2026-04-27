import Link from "next/link";
import { SignOutButton } from "@clerk/nextjs";
import { currentUser } from "@clerk/nextjs/server";
import { headers } from "next/headers";
import { isAdminClerkEmail } from "@/lib/admin-emails";
import { getStudioPublicOrigin } from "@/lib/studio-public-url";
import IntakeClient from "./intake-client";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type MetadataOk = {
  ok: true;
  secret_name: string;
  service: string;
  description: string | null;
  expected_prefix: string | null;
  status: string;
  expires_at: string;
};

type MetadataErr = {
  ok: false;
  statusCode: number;
  message: string;
};

async function resolveBaseUrl(): Promise<string> {
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host");
  if (!host) {
    return getStudioPublicOrigin();
  }
  const proto =
    h.get("x-forwarded-proto") ?? (host.startsWith("localhost") || host.startsWith("127.") ? "http" : "https");
  return `${proto}://${host}`;
}

async function loadMetadata(token: string): Promise<MetadataOk | MetadataErr> {
  const base = await resolveBaseUrl();
  const res = await fetch(`${base}/api/secrets/intake/${encodeURIComponent(token)}`, {
    cache: "no-store",
  });
  const json = (await res.json()) as {
    success?: boolean;
    error?: string;
    data?: {
      secret_name: string;
      service: string;
      description: string | null;
      expected_prefix: string | null;
      status: string;
      expires_at: string;
    };
  };

  if (!res.ok || !json.success || !json.data) {
    return {
      ok: false,
      statusCode: res.status,
      message: json.error ?? "Could not load intake",
    };
  }

  return {
    ok: true,
    ...json.data,
  };
}

export default async function SecretIntakePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const user = await currentUser();
  const email =
    user?.primaryEmailAddress?.emailAddress ?? user?.emailAddresses?.[0]?.emailAddress ?? null;

  if (!user || !email || !isAdminClerkEmail(email)) {
    return (
      <div className="space-y-4">
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          Secret intake
        </h1>
        <div className="rounded-xl border border-rose-800/40 bg-rose-950/20 p-6">
          <p className="text-rose-300">Not authorized</p>
          <p className="mt-2 text-sm text-zinc-400">
            This page is only available to founder admin accounts listed in{" "}
            <code className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-xs text-zinc-300">
              ADMIN_EMAILS
            </code>
            .
          </p>
          <SignOutButton signOutOptions={{ redirectUrl: "/sign-in" }}>
            <button
              type="button"
              className="mt-4 text-sm text-zinc-300 underline decoration-zinc-600 underline-offset-4 hover:text-white"
            >
              Sign out
            </button>
          </SignOutButton>
        </div>
      </div>
    );
  }

  const meta = await loadMetadata(token);

  if (!meta.ok) {
    const isGone = meta.statusCode === 410;
    return (
      <div className="space-y-4">
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          Secret intake
        </h1>
        <div
          className={`rounded-xl border p-6 ${isGone ? "border-zinc-700 bg-zinc-900/60" : "border-rose-800/40 bg-rose-950/20"}`}
        >
          <p className={isGone ? "text-zinc-300" : "text-rose-300"}>
            {isGone ? "This intake link is no longer valid." : meta.message}
          </p>
          <Link
            href="/admin/secrets"
            className="mt-4 inline-block text-sm text-zinc-400 underline decoration-zinc-600 underline-offset-4 hover:text-zinc-200"
          >
            Back to Secrets
          </Link>
        </div>
      </div>
    );
  }

  if (meta.status !== "pending") {
    return (
      <div className="space-y-4">
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          Secret intake
        </h1>
        <div className="rounded-xl border border-zinc-700 bg-zinc-900/60 p-6">
          <p className="text-zinc-300">This intake link is no longer valid.</p>
          <Link
            href="/admin/secrets"
            className="mt-4 inline-block text-sm text-zinc-400 underline decoration-zinc-600 underline-offset-4 hover:text-zinc-200"
          >
            Back to Secrets
          </Link>
        </div>
      </div>
    );
  }

  return (
    <IntakeClient
      token={token}
      secretName={meta.secret_name}
      service={meta.service}
      description={meta.description}
      expectedPrefix={meta.expected_prefix}
      expiresAt={meta.expires_at}
    />
  );
}

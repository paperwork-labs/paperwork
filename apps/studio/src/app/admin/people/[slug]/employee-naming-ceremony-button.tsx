"use client";

import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";

import { Sparkles } from "lucide-react";

import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@paperwork-labs/ui";

type BrainEnvelope = {
  success?: boolean;
  data?: { naming?: { display_name?: string; tagline?: string; avatar_emoji?: string } };
  error?: string;
};

export function EmployeeNamingCeremonyButton({
  slug,
  label = "Run Naming Ceremony",
}: {
  slug: string;
  label?: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runCeremony = useCallback(async () => {
    setPending(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/admin/employees/${encodeURIComponent(slug)}/name-ceremony`,
        { method: "POST" },
      );
      const json = (await res.json().catch(() => null)) as BrainEnvelope | null;
      if (!res.ok || json?.success === false) {
        setError(json?.error ?? `Request failed (${res.status})`);
        return;
      }
      setOpen(false);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setPending(false);
    }
  }, [router, slug]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="border-zinc-600 bg-zinc-900/80 text-zinc-100 hover:bg-zinc-800"
        onClick={() => setOpen(true)}
      >
        <Sparkles className="mr-2 h-4 w-4" aria-hidden />
        {label}
      </Button>
      <DialogContent className="border-zinc-800 bg-zinc-950 text-zinc-100 sm:rounded-xl">
        <DialogHeader>
          <DialogTitle className="text-zinc-50">Run naming ceremony?</DialogTitle>
          <DialogDescription className="text-zinc-400">
            Brain will pick a display name, tagline, and avatar emoji for{" "}
            <span className="font-mono text-zinc-300">{slug}</span> via its configured model,
            overwriting any current persona fields.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex-col gap-2 sm:flex-row sm:gap-0">
          {error ? (
            <p className="mr-auto w-full text-left text-sm text-rose-400 sm:order-first" role="alert">
              {error}
            </p>
          ) : null}
          <Button
            type="button"
            variant="outline"
            className="border-zinc-600 bg-transparent text-zinc-200 hover:bg-zinc-900"
            onClick={() => setOpen(false)}
            disabled={pending}
          >
            Cancel
          </Button>
          <Button
            type="button"
            className="bg-violet-600 text-white hover:bg-violet-500"
            onClick={() => void runCeremony()}
            disabled={pending}
          >
            {pending ? "Running…" : "Run ceremony"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

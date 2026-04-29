"use client";

import * as React from "react";
import { Upload } from "lucide-react";

import { cn } from "../lib/utils";
import { Progress } from "./progress";

export type DropZoneProps = {
  accept: string[];
  maxBytes: number;
  onUpload: (files: File[]) => Promise<void>;
  multiple?: boolean;
  children?: React.ReactNode;
};

function isAccepted(file: File, accept: string[]): boolean {
  if (accept.length === 0) return true;
  const mime = file.type.toLowerCase();
  return accept.some((pattern) => {
    const p = pattern.trim().toLowerCase();
    if (p === "*/*") return true;
    if (p.endsWith("/*")) {
      const prefix = p.slice(0, -1);
      return mime.startsWith(prefix);
    }
    return mime === p;
  });
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function DropZone({ accept, maxBytes, onUpload, multiple = false, children }: DropZoneProps) {
  const [dragOver, setDragOver] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [progress, setProgress] = React.useState<number | null>(null);
  const [previews, setPreviews] = React.useState<{ file: File; url: string }[]>([]);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const revokePreviews = React.useCallback(() => {
    setPreviews((prev) => {
      prev.forEach((p) => URL.revokeObjectURL(p.url));
      return [];
    });
  }, []);

  React.useEffect(() => () => revokePreviews(), [revokePreviews]);

  const validateFiles = React.useCallback(
    (files: File[]): File[] | null => {
      setError(null);
      const list = multiple ? files : files.slice(0, 1);
      if (list.length === 0) {
        setError("No files selected.");
        return null;
      }
      for (const f of list) {
        if (!isAccepted(f, accept)) {
          setError(`Unsupported type: ${f.name} (${f.type || "unknown"})`);
          return null;
        }
        if (f.size > maxBytes) {
          setError(`${f.name} exceeds max size ${formatBytes(maxBytes)}.`);
          return null;
        }
      }
      return list;
    },
    [accept, maxBytes, multiple],
  );

  const runUpload = React.useCallback(
    async (files: File[]) => {
      const ok = validateFiles(files);
      if (!ok) return;
      revokePreviews();
      const nextPreviews = ok
        .filter((f) => f.type.startsWith("image/"))
        .map((f) => ({ file: f, url: URL.createObjectURL(f) }));
      setPreviews(nextPreviews);
      setProgress(10);
      try {
        await onUpload(ok);
        setProgress(100);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed");
        setProgress(null);
        revokePreviews();
        return;
      }
      globalThis.setTimeout(() => setProgress(null), 400);
    },
    [onUpload, revokePreviews, validateFiles],
  );

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files ? Array.from(e.target.files) : [];
    void runUpload(files);
    e.target.value = "";
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    void runUpload(files);
  };

  const onPaste = React.useCallback(
    (e: React.ClipboardEvent) => {
      const items = e.clipboardData?.files;
      if (!items || items.length === 0) return;
      const files = Array.from(items);
      void runUpload(files);
    },
    [runUpload],
  );

  const defaultInner = (
    <div className="flex flex-col items-center gap-2 py-6 text-center text-sm text-muted-foreground">
      <Upload className="size-8 opacity-60" aria-hidden />
      <p>
        Drag files here, paste from clipboard, or{" "}
        <button
          type="button"
          className="font-medium text-primary underline"
          onClick={() => inputRef.current?.click()}
        >
          browse
        </button>
      </p>
      <p className="text-xs">Max {formatBytes(maxBytes)} per file</p>
    </div>
  );

  return (
    <div className="flex flex-col gap-3">
      <div
        role="button"
        tabIndex={0}
        className={cn(
          "rounded-lg border-2 border-dashed p-4 transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring",
          dragOver ? "border-primary bg-primary/5" : "border-muted-foreground/30 bg-muted/20",
          error && "border-destructive/60 bg-destructive/5",
        )}
        onPaste={onPaste}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
      >
        <input
          ref={inputRef}
          type="file"
          className="sr-only"
          accept={accept.join(",")}
          multiple={multiple}
          onChange={onInputChange}
        />
        {children ?? defaultInner}
      </div>
      {error ? (
        <div className="text-sm text-destructive" role="alert">
          {error}
        </div>
      ) : null}
      {progress != null ? (
        <div className="space-y-1" aria-live="polite">
          <Progress value={progress} className="h-2" />
          <p className="text-xs text-muted-foreground">Uploading…</p>
        </div>
      ) : null}
      {previews.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {previews.map((p) => (
            <img
              key={p.url}
              src={p.url}
              alt={p.file.name}
              className="h-16 w-16 rounded-md border object-cover"
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

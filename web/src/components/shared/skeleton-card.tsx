import { cn } from "@/lib/utils";

interface SkeletonCardProps {
  lines?: number;
  className?: string;
}

export function SkeletonCard({ lines = 3, className }: SkeletonCardProps) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border/50 bg-card p-6 space-y-3",
        className
      )}
    >
      <div className="h-4 w-2/5 animate-pulse rounded bg-muted" />
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-3 animate-pulse rounded bg-muted"
          style={{ width: `${70 + Math.random() * 25}%` }}
        />
      ))}
    </div>
  );
}

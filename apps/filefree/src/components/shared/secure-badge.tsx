import { Shield } from "lucide-react";
import { cn } from "@paperwork-labs/ui";

interface SecureBadgeProps {
  className?: string;
  text?: string;
}

export function SecureBadge({
  className,
  text = "Bank-level encryption",
}: SecureBadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-green-500/20 bg-green-500/10 px-3 py-1 text-xs font-medium text-green-400",
        className
      )}
    >
      <Shield className="h-3 w-3" />
      {text}
    </div>
  );
}

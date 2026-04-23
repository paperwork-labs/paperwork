import React from "react";
import { TrendingDown, TrendingUp } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { semanticTextColorClass } from "@/lib/semantic-text-color";

export interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  /** Compact = border box (dashboard style); full = KPI style without Chakra Stat primitives */
  variant?: "compact" | "full";
  trend?: "up" | "down";
  color?: string;
  helpText?: string;
  icon?: React.ElementType;
}

const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  sub,
  variant = "compact",
  trend,
  color,
  helpText,
  icon: Icon,
}) => {
  const valueColorClass = cn(semanticTextColorClass(color));

  if (variant === "full") {
    return (
      <div className="min-w-[140px] flex-1">
        <div className="mb-1 flex items-center gap-1">
          {Icon ? <Icon className="size-4 text-muted-foreground" aria-hidden /> : null}
          <span className="text-sm text-muted-foreground">{label}</span>
        </div>
        <p
          className={cn(
            "font-mono text-2xl leading-tight font-semibold tracking-tight text-foreground tabular-nums",
            valueColorClass
          )}
          aria-label={`${label}: ${value}`}
        >
          {value}
        </p>
        {(helpText !== undefined || sub) && (
          <div className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
            {trend === "up" ? (
              <TrendingUp className="size-3.5 text-[rgb(var(--status-success)/1)]" aria-hidden />
            ) : null}
            {trend === "down" ? (
              <TrendingDown className="size-3.5 text-[rgb(var(--status-danger)/1)]" aria-hidden />
            ) : null}
            <span>{helpText ?? sub}</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <Card
      variant="flat"
      size="none"
      className={cn(
        "min-w-[120px] flex-1 rounded-lg transition-transform duration-200",
        "hover:-translate-y-px"
      )}
    >
      <CardContent className="flex flex-col gap-1 px-3 py-3">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span
          className={cn(
            "font-mono text-lg leading-tight font-bold tracking-tight text-foreground tabular-nums",
            valueColorClass
          )}
          aria-label={`${label}: ${value}`}
        >
          {value}
        </span>
        {sub != null && sub !== "" ? (
          <span className="text-xs text-muted-foreground">{sub}</span>
        ) : null}
      </CardContent>
    </Card>
  );
};

export default StatCard;

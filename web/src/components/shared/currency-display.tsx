"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface CurrencyDisplayProps {
  cents: number;
  animate?: boolean;
  duration?: number;
  className?: string;
  prefix?: string;
}

export function CurrencyDisplay({
  cents,
  animate = true,
  duration = 1200,
  className,
  prefix = "$",
}: CurrencyDisplayProps) {
  const [displayed, setDisplayed] = useState(animate ? 0 : cents);

  useEffect(() => {
    if (!animate) {
      setDisplayed(cents);
      return;
    }

    const steps = 40;
    const increment = cents / steps;
    let step = 0;

    const interval = setInterval(() => {
      step++;
      setDisplayed(Math.min(Math.round(increment * step), cents));
      if (step >= steps) clearInterval(interval);
    }, duration / steps);

    return () => clearInterval(interval);
  }, [cents, animate, duration]);

  const formatted = (displayed / 100).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  return (
    <span className={cn("font-mono tabular-nums", className)}>
      {prefix}
      {formatted}
    </span>
  );
}

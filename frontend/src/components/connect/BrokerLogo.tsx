/**
 * BrokerLogo — renders an `<img>` for a broker SVG with a graceful
 * fallback monogram circle when the asset 404s.
 *
 * Why this exists: the broker catalog is the single source of truth for
 * which brokers we surface, but logo SVGs are checked into
 * `frontend/public/broker-logos/` separately. We deliberately do NOT
 * crash when an asset is missing — the page still has to render every
 * card. The fallback is a deterministic two-letter monogram against a
 * subtle muted background so the grid stays visually consistent even
 * before the real logo lands.
 */
import * as React from "react";

import { cn } from "@/lib/utils";

interface BrokerLogoProps {
  src: string;
  alt: string;
  monogram: string;
  size?: number;
  className?: string;
}

function deriveMonogram(name: string): string {
  // Strip parens / qualifiers ("(via SnapTrade)", "(one-click)") so the
  // monogram tracks the brand, not the modifier.
  const base = name.replace(/\(.*?\)/g, "").trim();
  const tokens = base.split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return "?";
  if (tokens.length === 1) return tokens[0].slice(0, 2).toUpperCase();
  return (tokens[0][0] + tokens[1][0]).toUpperCase();
}

export function BrokerLogo({ src, alt, monogram, size = 40, className }: BrokerLogoProps) {
  const [errored, setErrored] = React.useState(false);
  const initials = React.useMemo(
    () => deriveMonogram(monogram || alt),
    [monogram, alt],
  );

  if (errored) {
    return (
      <div
        role="img"
        aria-label={alt}
        className={cn(
          "flex shrink-0 items-center justify-center rounded-full bg-muted text-foreground/80 font-heading font-medium",
          className,
        )}
        style={{ width: size, height: size, fontSize: size * 0.35 }}
      >
        {initials}
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      width={size}
      height={size}
      onError={() => setErrored(true)}
      loading="lazy"
      decoding="async"
      className={cn("shrink-0 rounded-md object-contain", className)}
    />
  );
}

export default BrokerLogo;

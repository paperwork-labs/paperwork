/**
 * BrokerLogo — stable local SVG for known broker slugs; remote URL + monogram
 * when not bundled; Lucide Building2 when the slug is unknown and no URL.
 */
import * as React from "react";
import { Building2 } from "lucide-react";

import { cn } from "@/lib/utils";

import { resolveBrokerLogoUrl } from "./brokerLogosMap";

const LOGO_TILE = "shrink-0 rounded-md bg-muted/60 object-contain p-0.5";

function deriveMonogram(name: string): string {
  const base = name.replace(/\(.*?\)/g, "").trim();
  const tokens = base.split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return "?";
  if (tokens.length === 1) return tokens[0].slice(0, 2).toUpperCase();
  return (tokens[0][0] + tokens[1][0]).toUpperCase();
}

export type BrokerLogoProps = (
  | {
      /** Broker slug, e.g. from connection hub. */
      slug: string;
      /** Accessible / display name, e.g. "Charles Schwab". */
      name: string;
      /** When no local mark exists, try this first (e.g. `/broker-logos/vanguard.svg`). */
      remoteLogoUrl?: string;
      size?: number;
      className?: string;
    }
  | {
      /** Legacy: direct URL to an SVG. */
      src: string;
      alt: string;
      monogram: string;
      size?: number;
      className?: string;
    }
);

export function BrokerLogo(props: BrokerLogoProps) {
  if ("src" in props) {
    return (
      <LegacyRemoteBrokerLogo
        src={props.src}
        alt={props.alt}
        monogram={props.monogram}
        size={props.size}
        className={props.className}
      />
    );
  }
  return (
    <PrimaryBrokerLogo
      slug={props.slug}
      name={props.name}
      remoteLogoUrl={props.remoteLogoUrl}
      size={props.size}
      className={props.className}
    />
  );
}

function PrimaryBrokerLogo({
  slug,
  name,
  remoteLogoUrl,
  size = 40,
  className,
}: {
  slug: string;
  name: string;
  remoteLogoUrl?: string;
  size?: number;
  className?: string;
}) {
  const [remoteErrored, setRemoteErrored] = React.useState(false);
  const bundled = resolveBrokerLogoUrl(slug);
  const label = `${name} logo`;
  if (bundled) {
    return (
      <img
        src={bundled}
        alt={label}
        width={size}
        height={size}
        loading="lazy"
        decoding="async"
        className={cn(LOGO_TILE, className)}
      />
    );
  }
  if (remoteLogoUrl && !remoteErrored) {
    return (
      <img
        src={remoteLogoUrl}
        alt={label}
        width={size}
        height={size}
        loading="lazy"
        decoding="async"
        onError={() => setRemoteErrored(true)}
        className={cn(LOGO_TILE, className)}
      />
    );
  }
  if (remoteLogoUrl && remoteErrored) {
    return (
      <div
        role="img"
        aria-label={label}
        className={cn(
          "flex shrink-0 items-center justify-center rounded-md bg-muted text-foreground/80",
          "font-heading font-medium",
          className,
        )}
        style={{ width: size, height: size, fontSize: size * 0.35 }}
      >
        {deriveMonogram(name)}
      </div>
    );
  }
  return (
    <div
      role="img"
      aria-label={label}
      className={cn("flex shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground", className)}
      style={{ width: size, height: size }}
    >
      <Building2 className="size-[55%]" strokeWidth={1.75} aria-hidden />
    </div>
  );
}

function LegacyRemoteBrokerLogo({
  src,
  alt,
  monogram,
  size = 40,
  className,
}: {
  src: string;
  alt: string;
  monogram: string;
  size?: number;
  className?: string;
}) {
  const [errored, setErrored] = React.useState(false);
  const initials = React.useMemo(() => deriveMonogram(monogram || alt), [monogram, alt]);

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

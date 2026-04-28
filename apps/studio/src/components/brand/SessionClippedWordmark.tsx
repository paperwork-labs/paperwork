"use client";

import * as React from "react";
import Image from "next/image";

/**
 * Parent clipped lockup for Studio marketing surfaces — static locked raster.
 *
 * Previously drove a session-once entrance animation via the removed
 * `ClippedWordmark` component; that animation was dropped in favor of the
 * canonical PNG (`docs/brand/CANON.md`). Rebuilding entrance motion as a PNG
 * sprite sequence is queued under `t2-animation`, gated on the founder picking
 * the P5 sprite source.
 */
export function SessionClippedWordmark({
  className,
}: {
  className?: string;
}): React.ReactElement {
  return (
    <Image
      src="/brand/renders/paperclip-LOCKED-canonical-1024.png"
      alt="Paperwork Labs"
      width={1408}
      height={768}
      className={className}
      priority
    />
  );
}

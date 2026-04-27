"use client";

import { ClippedWordmark } from "@paperwork-labs/ui";

/** Parent clipped lockup for Studio auth — static (calmer than marketing header). */
export function StudioSignInBrand() {
  return (
    <div className="flex justify-center">
      <ClippedWordmark animated={false} surface="dark" />
    </div>
  );
}

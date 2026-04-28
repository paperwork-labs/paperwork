"use client";

import Image from "next/image";

/** Parent clipped lockup for Studio auth — static locked raster (calmer than marketing header). */
export function StudioSignInBrand() {
  return (
    <div className="flex justify-center">
      <Image
        src="/brand/renders/paperclip-LOCKED-canonical-1024.png"
        alt="Paperwork Labs"
        width={1408}
        height={768}
        className="h-14 w-auto"
        priority
      />
    </div>
  );
}

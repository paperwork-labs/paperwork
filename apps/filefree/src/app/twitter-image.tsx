import { ImageResponse } from "next/og";

import { filefreeBrandOg } from "@/lib/brand-locked-og";

export const runtime = "edge";
export const alt = "FileFree — Free AI Tax Filing";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: `linear-gradient(135deg, ${filefreeBrandOg.bgGradientStart} 0%, ${filefreeBrandOg.bgGradientMid} 50%, ${filefreeBrandOg.bgGradientEnd} 100%)`,
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "24px",
          }}
        >
          <div
            style={{
              fontSize: 72,
              fontWeight: 700,
              letterSpacing: "-0.025em",
              color: filefreeBrandOg.text,
              display: "flex",
            }}
          >
            File
            <span
              style={{
                background: `linear-gradient(to right, ${filefreeBrandOg.gradientFrom}, ${filefreeBrandOg.gradientTo})`,
                backgroundClip: "text",
                color: "transparent",
              }}
            >
              Free
            </span>
          </div>
          <div
            style={{
              fontSize: 32,
              fontWeight: 500,
              color: filefreeBrandOg.textMuted,
              textAlign: "center",
              maxWidth: "700px",
              display: "flex",
            }}
          >
            Snap your W-2. Get your return in minutes. Actually free.
          </div>
          <div
            style={{
              marginTop: "16px",
              padding: "12px 32px",
              borderRadius: "8px",
              background: `linear-gradient(to right, ${filefreeBrandOg.gradientFrom}, ${filefreeBrandOg.gradientTo})`,
              color: filefreeBrandOg.text,
              fontSize: 20,
              fontWeight: 600,
              display: "flex",
            }}
          >
            filefree.ai
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}

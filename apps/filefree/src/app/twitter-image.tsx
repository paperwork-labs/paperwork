import { ImageResponse } from "next/og";

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
          background: "linear-gradient(135deg, #020817 0%, #0f172a 50%, #1e1b4b 100%)",
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
              color: "#e2e8f0",
              display: "flex",
            }}
          >
            File
            <span
              style={{
                background: "linear-gradient(to right, #8b5cf6, #9333ea)",
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
              color: "#94a3b8",
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
              background: "linear-gradient(to right, #7c3aed, #9333ea)",
              color: "#ffffff",
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

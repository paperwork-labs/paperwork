import type { MetadataRoute } from "next";

import { buildManifest } from "@paperwork-labs/pwa";

// Track M.7 — Studio as an installable Chrome app.
//
// Next.js picks up ``app/manifest.ts`` automatically and serves the
// result at ``/manifest.webmanifest``. We lean on the shared
// ``buildManifest`` helper so Studio and AxiomFolio agree on the
// defaults (display: standalone, start_url: /, etc.) and only differ
// in the values that should differ (name, theme color, icons).
export default function manifest(): MetadataRoute.Manifest {
  return buildManifest({
    name: "Paperwork Studio",
    shortName: "Studio",
    description:
      "Command center for Paperwork Labs — personas, medallion DAGs, cost dashboards, and runbooks.",
    startUrl: "/admin",
    scope: "/",
    themeColor: "#0F172A",
    backgroundColor: "#0F172A",
    categories: ["productivity", "business"],
    // Icon assets live in /apps/studio/public/icons/ — we reference a
    // minimal 512×512 set to match AxiomFolio's pattern. Add additional
    // sizes (192, 384) as they're generated.
    icons: [
      {
        src: "/icons/studio-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/studio-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/studio-512-maskable.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  }) as MetadataRoute.Manifest;
}

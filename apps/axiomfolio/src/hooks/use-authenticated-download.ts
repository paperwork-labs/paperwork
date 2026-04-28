"use client";

import { useCallback } from "react";
import { useAuth } from "@clerk/nextjs";

/**
 * Download a same-origin or API URL with the same Bearer token axios uses,
 * avoiding `window.open` which does not attach `Authorization`.
 */
export function useAuthenticatedDownload() {
  const { getToken } = useAuth();

  const download = useCallback(
    async (url: string, filename: string) => {
      const headers: HeadersInit = {
        Accept: "text/csv,application/octet-stream,*/*",
      };
      const token = await getToken();
      if (token) {
        (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch(url, {
        method: "GET",
        credentials: "include",
        headers,
      });

      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(text || `Download failed (${res.status})`);
      }

      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      try {
        const a = document.createElement("a");
        a.href = objectUrl;
        a.download = filename;
        a.rel = "noopener";
        document.body.appendChild(a);
        a.click();
        a.remove();
      } finally {
        URL.revokeObjectURL(objectUrl);
      }
    },
    [getToken],
  );

  return { download };
}

/**
 * Base URL for links returned by the Studio API (intake URLs, etc.).
 */
export function getStudioPublicOrigin(): string {
  const explicit = process.env.STUDIO_URL?.trim();
  if (explicit) {
    return explicit.replace(/\/$/, "");
  }
  const vercel = process.env.VERCEL_URL?.trim();
  if (vercel) {
    const host = vercel.startsWith("http") ? vercel : `https://${vercel}`;
    return host.replace(/\/$/, "");
  }
  return "https://paperworklabs.com";
}

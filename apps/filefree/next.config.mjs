import { withSentryConfig } from "@sentry/nextjs";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  transpilePackages: ["@paperwork-labs/ui"],
  async redirects() {
    // Next.js maps permanent: true to HTTP 308 (and temporary to 307), not 301/302.
    return [
      {
        source: "/:path*",
        has: [{ type: "host", value: "filefree.tax" }],
        destination: "https://filefree.ai/:path*",
        permanent: true,
      },
      {
        source: "/:path*",
        has: [{ type: "host", value: "www.filefree.tax" }],
        destination: "https://filefree.ai/:path*",
        permanent: true,
      },
    ];
  },
};

export default withSentryConfig(nextConfig, {
  silent: !process.env.CI,
  disableLogger: true,
});

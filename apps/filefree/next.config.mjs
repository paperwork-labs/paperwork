import { withSentryConfig } from "@sentry/nextjs";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  transpilePackages: ["@paperwork-labs/ui"],
  async redirects() {
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

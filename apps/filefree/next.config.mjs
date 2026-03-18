import { withSentryConfig } from "@sentry/nextjs";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  transpilePackages: ["@venture/ui"],
};

export default withSentryConfig(nextConfig, {
  silent: !process.env.CI,
  disableLogger: true,
});

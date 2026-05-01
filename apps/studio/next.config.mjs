/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  transpilePackages: ["@paperwork-labs/ui"],
  async redirects() {
    return [
      // Legacy routes folded into Architecture / Infrastructure / Brain shells
      // (WS-69 PR C). permanent: true = 308 Permanent Redirect.
      {
        source: "/admin/workflows",
        destination: "/admin/architecture?tab=flows",
        permanent: true,
      },
      {
        source: "/admin/n8n-mirror",
        destination: "/admin/architecture?tab=flows",
        permanent: true,
      },
      {
        source: "/admin/automation",
        destination: "/admin/architecture?tab=flows",
        permanent: true,
      },
      {
        source: "/admin/analytics",
        destination: "/admin/architecture?tab=analytics",
        permanent: true,
      },
      {
        source: "/admin/secrets",
        destination: "/admin/infrastructure?tab=secrets",
        permanent: true,
      },
      {
        source: "/admin/founder-actions",
        destination: "/admin/brain/conversations?filter=needs-action",
        permanent: true,
      },
      {
        source: "/admin/brain-learning",
        destination: "/admin/brain/self-improvement?tab=learning",
        permanent: true,
      },
      {
        source: "/admin/sprints",
        has: [{ type: "query", key: "tab", value: "cycles" }],
        destination: "/admin/workstreams?tab=cycles",
        permanent: true,
      },
      {
        source: "/admin/sprints",
        destination: "/admin/workstreams?tab=sprints",
        permanent: true,
      },
      {
        source: "/admin/pr-pipeline",
        destination: "/admin/workstreams?tab=pr-pipeline",
        permanent: true,
      },
      {
        source: "/admin/money/bills",
        destination: "/admin/bills",
        permanent: true,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;

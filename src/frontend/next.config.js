/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // OAuth callback queries contain single-use codes and state. Next's dev
  // request logger prints full URLs; backend telemetry provides safe events.
  logging: { incomingRequests: { ignore: [/^\/api\/v1\/auth(?:\/|\?|$)/] } },
  turbopack: { root: __dirname },
  async rewrites() {
    // Vercel Services handles this prefix in production; local dev stays same-origin.
    if (process.env.NODE_ENV !== "development") return [];
    return [{ source: "/api/v1/:path*", destination: "http://127.0.0.1:8000/api/v1/:path*" }];
  },
};

module.exports = nextConfig;

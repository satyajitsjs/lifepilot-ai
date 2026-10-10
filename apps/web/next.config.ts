import type { NextConfig } from "next";

// In Vercel, set API_BACKEND_URL to the public FastAPI origin.
// In Docker, the upstream is http://api:8000 (configured at image build time).
// The browser always calls same-origin /api/*.
const apiBackend = (process.env.API_BACKEND_URL || "http://127.0.0.1:8000")
  .trim()
  .replace(/\/+$/, "");

if (!/^https?:\/\/[^/?#]+$/.test(apiBackend)) {
  throw new Error("API_BACKEND_URL must be an http(s) origin without a path or query.");
}

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiBackend}/api/:path*` },
      { source: "/healthz", destination: `${apiBackend}/healthz` },
    ];
  },
};

export default nextConfig;

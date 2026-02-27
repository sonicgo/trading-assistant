import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* Proxy Configuration - Docker Compose networking */
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://api:8000/api/v1/:path*',
      },
    ];
  },

  /* Behavior Fixes */
  trailingSlash: false,

  /* Next.js 15/16 standard keys */
  serverExternalPackages: [],
};

export default nextConfig;

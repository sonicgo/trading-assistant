import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* Proxy Configuration */
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://localhost:8000/api/v1/:path*',
      },
    ];
  },

  /* Behavior Fixes */
  trailingSlash: false, // Prevents the 308/307 redirect chain

  /* Next.js 15/16 standard keys */
  serverExternalPackages: [], // Moved from experimental to root
  
  devIndicators: {
    appIsrStatus: false, // Disables the ISR status indicator
    buildActivity: true,
  },
};

export default nextConfig;
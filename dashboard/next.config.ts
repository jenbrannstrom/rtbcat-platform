import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  devIndicators: false,
  async redirects() {
    return [
      {
        source: "/creatives",
        destination: "/clusters",
        permanent: false,
      },
    ];
  },
  async rewrites() {
    // When OAUTH2_PROXY_MODE is set (GCP deployment), don't rewrite API calls.
    // Let them go through nginx → OAuth2 Proxy → API so the X-Email header is set.
    if (process.env.OAUTH2_PROXY_MODE === "true") {
      return [];
    }

    // Development mode: proxy API calls directly to the API container
    const apiHost = process.env.API_HOST || "localhost";
    return [
      {
        source: "/api/:path*",
        destination: `http://${apiHost}:8000/:path*`,
      },
      {
        source: "/thumbnails/:path*",
        destination: `http://${apiHost}:8000/thumbnails/:path*`,
      },
    ];
  },
};

export default nextConfig;

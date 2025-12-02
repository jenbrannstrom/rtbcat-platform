import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  devIndicators: false,
  async rewrites() {
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

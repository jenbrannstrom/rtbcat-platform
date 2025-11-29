import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    const apiHost = process.env.API_HOST || "localhost";
    return [
      {
        source: "/api/:path*",
        destination: `http://${apiHost}:8000/:path*`,
      },
    ];
  },
};

export default nextConfig;

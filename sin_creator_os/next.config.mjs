/** @type {import('next').NextConfig} */
const apiBaseUrl = (process.env.API_INTERNAL_URL || "http://api:8000").replace(/\/+$/, "");

const nextConfig = {
  output: "standalone",
  reactCompiler: true,
  compiler: {
    removeConsole: process.env.NODE_ENV === "production",
  },
  async rewrites() {
    return [
      {
        source: "/v1/:path*",
        destination: `${apiBaseUrl}/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;

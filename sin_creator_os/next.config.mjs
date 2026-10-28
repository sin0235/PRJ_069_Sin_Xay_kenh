/** @type {import('next').NextConfig} */
const apiBaseUrl = (process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

const nextConfig = {
  allowedDevOrigins: [
    "192.168.1.175",
    "192.168.1.175:3069",
    "localhost",
    "localhost:3000",
    "localhost:3069",
    "nhap-xaykenh-proj069.bahagroup.vn",
    "*.bahagroup.vn",
  ],
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

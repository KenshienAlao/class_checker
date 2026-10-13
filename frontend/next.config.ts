import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  compiler: {
    removeConsole: {
      exclude: ["error", "warn"],
    },
  },
};

export default nextConfig;

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The dev server only trusts "localhost" by default; opening the page by 127.0.0.1 (or a LAN name)
  // makes it block its own hot-reload socket and fill the console with errors.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;

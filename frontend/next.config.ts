import type { NextConfig } from "next";

// "standalone" builds the small server bundle the Docker image runs.
// "export" builds a static site for S3 + CloudFront; set by scripts/deploy-frontend.sh.
const output =
  (process.env.NEXT_OUTPUT as "standalone" | "export") ?? "standalone";

const nextConfig: NextConfig = {
  output,
  // Bottom-left is where the icon rail keeps "Log out".
  devIndicators: { position: "bottom-right" },
  // The export target has no server to optimize images on the fly.
  ...(output === "export" ? { images: { unoptimized: true } } : {}),
};

export default nextConfig;

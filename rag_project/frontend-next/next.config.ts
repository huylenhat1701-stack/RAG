import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["react-markdown", "remark-math", "rehype-katex", "remark-gfm"],
};

export default nextConfig;

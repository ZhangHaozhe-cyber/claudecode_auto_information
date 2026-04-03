/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',        // static export for Cloudflare Pages
  trailingSlash: true,     // /route/ → index.html, required for Cloudflare Pages
  images: {
    unoptimized: true,     // no Image Optimization API in static export
  },
};

export default nextConfig;

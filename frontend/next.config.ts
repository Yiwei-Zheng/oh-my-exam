import type { NextConfig } from 'next'

const apiTarget = process.env.OME_API_PROXY_TARGET || 'http://127.0.0.1:8000'
const allowedDevOrigins = (process.env.OME_ALLOWED_DEV_ORIGINS || '')
  .split(',')
  .map((origin) => origin.trim())
  .filter(Boolean)

const nextConfig: NextConfig = {
  allowedDevOrigins,
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${apiTarget}/api/:path*` }]
  },
}

export default nextConfig

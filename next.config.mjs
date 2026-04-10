/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactCompiler: true,
  serverExternalPackages: ['electron'],
  outputFileTracingIncludes: {
    '*': ['public/**/*', '.next/static/**/*'],
  },
};

export default nextConfig;

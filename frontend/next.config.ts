import type { NextConfig } from 'next';

const config: NextConfig = {
  agentRules: false,
  experimental: {
    agentUpgrade: 'security',
  },
};

export default config;

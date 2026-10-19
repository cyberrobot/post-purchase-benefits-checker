import type { Config } from 'jest';
import nextJest from 'next/jest.js';

const createJestConfig = nextJest({ dir: './' });
const config: Config = {
  testEnvironment: 'jsdom',
  testPathIgnorePatterns: ['/node_modules/', '<rootDir>/e2e/'],
  setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
  moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' },
};

export default createJestConfig(config);

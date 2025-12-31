module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/electron', '<rootDir>/lib', '<rootDir>/scripts', '<rootDir>/app'],
  testMatch: ['**/__tests__/**/*.ts', '**/?(*.)+(spec|test).ts'],
  collectCoverageFrom: [
    'electron/**/*.ts',
    'lib/**/*.ts',
    'scripts/**/*.ts',
    'app/api/**/*.ts',
    '!**/*.d.ts',
    '!**/__tests__/**',
    '!**/__mocks__/**',
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html'],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {
      tsconfig: {
        jsx: 'react',
        esModuleInterop: true,
        allowSyntheticDefaultImports: true,
      }
    }],
  },
  // Transform ESM packages from node_modules
  transformIgnorePatterns: [
    'node_modules/(?!(wagmi|viem|@wagmi|@rainbow-me|@tanstack)/)',
  ],
  verbose: true,
  moduleNameMapper: {
    '^electron$': '<rootDir>/electron/__mocks__/electron.ts',
    '^@/(.*)$': '<rootDir>/$1',
    // Mock wagmi and viem to avoid ESM issues in tests
    '^wagmi$': '<rootDir>/lib/web3/__mocks__/wagmi.ts',
    '^wagmi/chains$': '<rootDir>/lib/web3/__mocks__/wagmi-chains.ts',
    '^viem$': '<rootDir>/lib/web3/__mocks__/viem.ts',
    '^@rainbow-me/rainbowkit$': '<rootDir>/lib/web3/__mocks__/rainbowkit.ts',
  },
};


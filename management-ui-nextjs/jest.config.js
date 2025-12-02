module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/electron', '<rootDir>/lib', '<rootDir>/scripts'],
  testMatch: ['**/__tests__/**/*.ts', '**/?(*.)+(spec|test).ts'],
  collectCoverageFrom: [
    'electron/**/*.ts',
    'lib/**/*.ts',
    'scripts/**/*.ts',
    '!**/*.d.ts',
    '!**/__tests__/**',
    '!**/__mocks__/**',
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html'],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  transform: {
    '^.+\\.ts$': 'ts-jest',
  },
  verbose: true,
  moduleNameMapper: {
    '^electron$': '<rootDir>/electron/__mocks__/electron.ts',
  },
};


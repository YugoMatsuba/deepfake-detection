/** @type {import('jest').Config} */
export default {
  testEnvironment: 'node',
  roots: ['<rootDir>/tests/integration'],
  moduleFileExtensions: ['js'],
  testTimeout: 30000,
};

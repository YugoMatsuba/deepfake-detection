import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs['recommended-latest'],
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: {
        ...globals.browser,
        process: 'readonly',  // Allow process.env in React code
      },
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]', argsIgnorePattern: '^_' }],
      'react-refresh/only-export-components': ['warn'],  // Downgrade to warning
    },
  },
  // Configuration for test files
  {
    files: ['**/*.test.{js,jsx}', '**/tests/**/*.{js,jsx}'],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.jest,
        ...globals.node,
      },
    },
  },
  // Configuration for config files (vite, jest, etc.)
  {
    files: ['*.config.{js,mjs}', 'vite.config.js'],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
  },
])

import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // 現有程式碼的 any 改為 warning，不阻擋 commit
      '@typescript-eslint/no-explicit-any': 'warn',
      // React 19 新規則：setState in effect 改為 warning（未來再重構）
      'react-hooks/set-state-in-effect': 'warn',
      // 忽略未使用的變數（以 _ 前綴命名）
      '@typescript-eslint/no-unused-vars': ['error', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        caughtErrorsIgnorePattern: '^_',
      }],
      // AuthContext 同時 export component 和 hook，允許此模式
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    },
  },
])

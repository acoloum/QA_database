/**
 * ESLint strict config for staged NEW files.
 * 新增檔案的 any 型別會被阻擋（error 等級）。
 * 不使用 type-aware rules，因為新檔案可能不在 tsconfig.project 中。
 */
import tseslint from 'typescript-eslint';

export default [
  // 包含 @typescript-eslint plugin
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
      // _ 前綴的未使用變數例外
      '@typescript-eslint/no-unused-vars': ['error', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        caughtErrorsIgnorePattern: '^_',
      }],
    },
  },
];

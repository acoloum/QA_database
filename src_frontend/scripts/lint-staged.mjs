import { execSync } from 'child_process';
import { ESLint } from 'eslint';

const newFiles = execSync('git diff --cached --name-only --diff-filter=A', { encoding: 'utf-8' })
  .trim()
  .split('\n')
  .filter(f => f && /\.(ts|tsx)$/.test(f));

const allStagedFiles = execSync('git diff --cached --name-only', { encoding: 'utf-8' })
  .trim()
  .split('\n')
  .filter(f => f && /\.(ts|tsx)$/.test(f));

const existingFiles = allStagedFiles.filter(f => !newFiles.includes(f));

const results = [];

// 新檔案：error 等級
if (newFiles.length > 0) {
  const eslintNew = new ESLint({
    baseConfig: {
      rules: { '@typescript-eslint/no-explicit-any': 'error' },
    },
    useEslintrc: false,
    extensions: ['.ts', '.tsx'],
  });
  results.push(await eslintNew.lintFiles(newFiles));
}

// 現有檔案：warning 等級
if (existingFiles.length > 0) {
  const eslintExisting = new ESLint({
    baseConfig: {
      rules: { '@typescript-eslint/no-explicit-any': 'warn' },
    },
    useEslintrc: false,
    extensions: ['.ts', '.tsx'],
  });
  results.push(await eslintExisting.lintFiles(existingFiles));
}

const { FlatCompat } = await import('@eslint/eslintrc');
const compat = new FlatCompat({
  baseDirectory: process.cwd(),
  recommendedConfig: (await import('@eslint/js')).default.configs.recommended,
});

const eslint = new ESLint({
  overrideConfigFile: true,
  overrideConfig: [
    ...(await compat.config({
      extends: ['typescript-eslint/recommended-type-checked'],
    })),
    {
      rules: {
        '@typescript-eslint/no-explicit-any': 'warn',
      },
    },
  ],
});

const flatResults = results.flat();
if (flatResults.length > 0) {
  const { Linter } = await import('eslint');
  const linter = new Linter();
  // Output via eslint formatter
  const formatter = await eslint.loadFormatter();
  const output = formatter.format(flatResults);
  if (output) console.log(output);
  const hasErrors = flatResults.some(r => r.errorCount > 0);
  if (hasErrors) process.exit(1);
}

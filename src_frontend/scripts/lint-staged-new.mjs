/**
 * lint-staged 鉤子
 * - 新增檔案：any → error（阻擋 commit）
 * - 既有毒禁用：any → warning（不阻擋）
 */
import { execSync } from 'child_process';
import { ESLint } from 'eslint';
import { resolve, isAbsolute } from 'path';
import { fileURLToPath } from 'url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const ROOT = resolve(__dirname, '..'); // C:\QC_Database\src_frontend\
const REL_PREFIX = 'src_frontend/';     // git 輸出相對於 repo root，需去掉此前綴

const exec = (cmd) => execSync(cmd, { encoding: 'utf-8', maxBuffer: 10 * 1024 * 1024 }).trim();

/** git 輸出 `src_frontend/xxx.ts`，去掉前綴後轉為絕對路徑 */
const toAbs = (f) => {
  const rel = f.startsWith(REL_PREFIX) ? f.slice(REL_PREFIX.length) : f;
  return resolve(ROOT, rel);
};

// 取得 staged 的新檔案
const newFiles = exec('git diff --cached --name-only --diff-filter=A')
  .split('\n')
  .filter(f => f && /\.(ts|tsx)$/.test(f))
  .map(toAbs);

// 取得 staged 的所有 TS/TSX 檔
const allStaged = exec('git diff --cached --name-only')
  .split('\n')
  .filter(f => f && /\.(ts|tsx)$/.test(f))
  .map(toAbs);

const existingFiles = allStaged.filter(f => !newFiles.includes(f));

const allResults = [];

// ① 既有毒禁用：用專案 eslintrc（warning）
if (existingFiles.length > 0) {
  const eslint = new ESLint({});
  allResults.push(...await eslint.lintFiles(existingFiles));
}

// ② 新增檔案：error 等級
const newFileSet = new Set(newFiles);
if (newFiles.length > 0) {
  const eslintStrict = new ESLint({
    overrideConfigFile: './scripts/eslint.staged.config.mjs',
  });
  const strictResults = await eslintStrict.lintFiles(newFiles);
  for (const r of strictResults) {
    if (newFileSet.has(r.filePath) && r.errorCount > 0) {
      allResults.push(r);
    }
  }
}

// 格式化輸出
const formatter = await new ESLint({}).loadFormatter();
const output = formatter.format(allResults);
if (output) console.log(output);

const hasBlockingErrors = allResults.some(r => r.errorCount > 0);
if (hasBlockingErrors) {
  console.log('\n❌ 新增 TS/TSX 檔案含有 any 型別或未使用變數，請修正後再 commit。\n');
  process.exit(1);
}

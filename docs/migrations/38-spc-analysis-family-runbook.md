# Migration 38：SPC 分析族別套用手冊

本 migration 為 `SPC研究`、`SPC界限版本` 增加受控 `分析族別`，為
`SPC研究版本` 增加不可變 `分析選項快照`，並將研究自然鍵、查詢索引與單一
active 界限索引納入分析族別。腳本位於
`backend/migration/38_add_spc_analysis_family.sql`，所有 DDL 都在單一交易內，
遇到 preflight 失敗會整體回滾，不得手動刪除或合併研究證據。

## 先決條件

- 使用 repo 根目錄 `C:\QC_Database\.env` 的 `DB_HOST`、`DB_PORT`、
  `DB_NAME`、`DB_USER`、`DB_PASSWORD`；不得將密碼寫入命令歷程、文件或輸出。
- 確認 PostgreSQL 18 `psql`：
  `C:\Program Files\PostgreSQL\18\bin\psql.exe`。
- 確認最近每日備份存在、可讀且大小不為零。2026-07-19 正式執行前確認：
  `C:\QC_Database\database_backup\backups\qa_backup_20260719_020003.dump`，
  修改時間 `2026-07-19 02:00:04`，大小 `2,035,544 bytes`。
- 正式套用前先完成下列 rollback dry-run；任何錯誤都必須停止，不可直接修改資料規避。

## 安全讀取連線設定

以下函式只把 `.env` 值放入目前 PowerShell process，不輸出值：

```powershell
function Read-DotEnv([string]$Path) {
    $map = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $parts = $line -split '=', 2
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $map[$key] = $value
    }
    return $map
}

$cfg = Read-DotEnv 'C:\QC_Database\.env'
Set-Item -Path Env:PGPASSWORD -Value $cfg['DB_PASSWORD']
$env:PGCLIENTENCODING = 'UTF8'
$psql = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
```

## Rollback dry-run

dry-run 檔只能建立在目前 worktree 的 `tmp\migration`。此檔是 migration 的機械
複本，唯一差異是交易結尾由 `COMMIT` 改為 `ROLLBACK`：

```powershell
$wt = (Resolve-Path -LiteralPath 'C:\QC_Database\.worktrees\advanced-spc-2026-2').Path.TrimEnd('\')
$tmp = Join-Path $wt 'tmp\migration'
New-Item -ItemType Directory -Path $tmp -Force | Out-Null
$source = Join-Path $wt 'backend\migration\38_add_spc_analysis_family.sql'
$dry = Join-Path $tmp '38_dry_run.sql'
$content = Get-Content -LiteralPath $source -Raw
if (([regex]::Matches($content, '(?m)^COMMIT;$')).Count -ne 1) {
    throw 'migration 38 的 COMMIT 數量不是 1'
}
$dryContent = [regex]::Replace($content, '(?m)^COMMIT;$', 'ROLLBACK;')
Set-Content -LiteralPath $dry -Value $dryContent -Encoding utf8NoBOM
$resolved = (Resolve-Path -LiteralPath $dry).Path
if (-not $resolved.StartsWith($wt + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'dry-run 路徑不在 worktree 內'
}
if ((Select-String -LiteralPath $resolved -Pattern '^COMMIT;$').Count -ne 0 -or
    (Select-String -LiteralPath $resolved -Pattern '^ROLLBACK;$').Count -ne 1) {
    throw 'dry-run transaction 結尾驗證失敗'
}

& $psql -X -v ON_ERROR_STOP=1 `
    -h $cfg['DB_HOST'] -p $cfg['DB_PORT'] `
    -U $cfg['DB_USER'] -d $cfg['DB_NAME'] `
    -f $resolved
if ($LASTEXITCODE -ne 0) { throw 'migration 38 dry-run 失敗' }
```

成功輸出必須以 `ROLLBACK` 結束。2026-07-19 執行證據：路徑 prefix 驗證通過，
`COMMIT=0`、`ROLLBACK=1`，全部 DDL 與 preflight 完成後 `ROLLBACK`，結果 PASS。

## 正式套用與 idempotent 重跑

```powershell
$migration = 'C:\QC_Database\.worktrees\advanced-spc-2026-2\backend\migration\38_add_spc_analysis_family.sql'

& $psql -X -v ON_ERROR_STOP=1 `
    -h $cfg['DB_HOST'] -p $cfg['DB_PORT'] `
    -U $cfg['DB_USER'] -d $cfg['DB_NAME'] `
    -f $migration
if ($LASTEXITCODE -ne 0) { throw 'migration 38 正式套用失敗' }

# 第二次完整重跑必須成功，用來驗證 idempotent。
& $psql -X -v ON_ERROR_STOP=1 `
    -h $cfg['DB_HOST'] -p $cfg['DB_PORT'] `
    -U $cfg['DB_USER'] -d $cfg['DB_NAME'] `
    -f $migration
if ($LASTEXITCODE -ne 0) { throw 'migration 38 第二次重跑失敗' }

Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
```

2026-07-19 對 `qa_database` 的首次套用與第二次重跑皆 `COMMIT` 成功；第二次只有
三個 `ADD COLUMN IF NOT EXISTS` 的 already-exists notice，沒有錯誤或人工資料修補。

## 套用後查核

必須確認：

- `SPC研究.分析族別`、`SPC界限版本.分析族別` 為 `NOT NULL DEFAULT 'variable'`；
- `SPC研究版本.分析選項快照` 為 `NOT NULL DEFAULT '{}'::jsonb`；
- `uq_spc_study_identity`、`idx_spc_study_stream_characteristic`、
  `uq_spc_one_active_limit` 都包含 `分析族別`；
- `trg_spc_limit_version_immutable`、`trg_spc_study_version_immutable` 維持原狀；
- 不支援族別、NULL、研究自然鍵重複、active 界限重複均為 0。

2026-07-19 查核結果：PostgreSQL `18.1`、目標 `qa_database`；三欄皆符合上述
nullable/default 契約；constraint 與兩個 index 正確；兩個 immutable trigger 均為
`O`；unsupported `0/0`、NULL `0/0/0`、重複研究 `0`、重複 active 界限 `0`。
`SPC軟體確效執行` 表也已存在。

## 暫存檔清理

取得證據後只能清理由上述 prefix 驗證過的 worktree 暫存檔。刪除不可復原，但檔案
可由 committed migration 重新產生，且不包含業務資料：

```powershell
$wt = (Resolve-Path -LiteralPath 'C:\QC_Database\.worktrees\advanced-spc-2026-2').Path.TrimEnd('\')
$target = (Resolve-Path -LiteralPath (Join-Path $wt 'tmp\migration')).Path
if (-not $target.StartsWith($wt + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw '拒絕清理 worktree 外路徑'
}
Remove-Item -LiteralPath (Join-Path $target '38_dry_run.sql') -Force
Remove-Item -LiteralPath $target -Force
$tmpRoot = Join-Path $wt 'tmp'
if ((Get-ChildItem -LiteralPath $tmpRoot -Force | Measure-Object).Count -eq 0) {
    Remove-Item -LiteralPath $tmpRoot -Force
}
```

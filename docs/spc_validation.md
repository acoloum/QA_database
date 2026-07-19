# SPC 分析軟體確效文件（AIAG & VDA SPC 2026.2）

本文件定義出貨檢驗與巡檢 SPC 的受控計算方法、輸入證據、適用門檻及可重現驗證方式。正式判定來源只存在於後端研究版本；前端不得重算或覆蓋穩定性結果。

## 受控方法

| 項目 | 2026.2 實作 | 不適用時的處理 |
|---|---|---|
| 製程流 | 來源、完整篩選、品質特性、來源記錄／量測 ID、規格與排除快照共同形成製程流與 SHA-256 資料雜湊 | 篩選或來源資料改變後不得沿用原送審雜湊 |
| 管制圖選型 | 所有子組 `n≥3` 優先 X̄-S；所有子組 `n=2` 使用 X̄-R；所有子組 `n=1` 且時間嚴格遞增使用 I-MR | 混合 `n=2` 與 `n≥3`、缺少時間或變異為零時回傳明確原因碼，不補造界限 |
| 不等子組 | X̄-S 依每組實際 `n` 計算位置與變異 UCL／CL／LCL | 不使用平均 `n` 代替逐點界限 |
| 穩定性 | 位置圖與變異圖分開執行受控規則；非對稱 S/R 界限的上、下區域寬度分別由 UCL／LCL 推導，再以兩圖共同結果判定研究穩定性 | 任一圖失控即不得宣告製程穩定 |
| 分布 | 常態以 Anderson-Darling；正值非常態可評估對數常態；形狀公差評估摺疊常態 | 沒有候選通過、樣本不足或退化資料時標示 `DISTRIBUTION_UNCONFIRMED` 等原因，不回退常態 |
| 時間模型 | 系統提出 A1、A2、B、C1～C4 或 D 候選；A1/A2 仍須具權限人員填理由確認 | 未確認或候選不是 A1/A2 時不報告 Cp/Cpk |
| 能力／績效 | 已接受分布可報告 Pp/Ppk；僅兩圖穩定且確認 A1/A2 時另報告 Cp/Cpk | 變異圖失控時，即使位置圖穩定，Cp/Cpk 仍為空 |
| 單側規格 | 只計算對應側 Ppu/Ppl、Ppk；能力適用時對應 Cpu/Cpl、Cpk | 不以不存在的另一側界限計算雙側指數 |
| PPM | 僅依已接受分布的尾端機率 | 分布未確認時 upper/lower/total 均為 `null` |
| 離群值 | 排除與恢復都必填理由，保存操作者、時間、舊值與新值；歷史研究保留當時快照 | 不刪除量測或先前稽核紀錄 |
| 正式界限 | 候選研究版本送審後，由 `spc.approve` 核准生效；同一製程流／特性只有一個 active 版 | 舊 `SPC管制界限` 僅匯入 `legacy_imported`，不可偽造核准人或直接啟用 |
| 正式失控事件 | 只有持續 SPC 使用 active 界限時建立去重事件，研究、事件與 audit 在同一交易提交；後續以 OCAP 保存 6M、重測、調整、產品處置、責任人與有效性 | 回溯研究只顯示診斷違規，不自動建立 OCAP；OCAP 可受控更新但不可刪除 |
| 持續監控 | 目前資料只計算觀測統計量，沿用核准版本的逐點界限與規則集；子組大小或圖表類型未被核准時拒絕監控 | 零變異仍是合法觀測資料；不因新增觀測值重新置中、重估變異或重算界限 |
| 屬性管制圖 | 只使用出貨／巡檢可由保存量測與規格可靠重建的符合／不符合單位，提供 p／np 與精確二項界限 | 分類不明資料 fail-closed 排除；不使用 NCMR、不實作 c／u；np 子組大小不固定時拒絕 |
| 機器績效 | 只接受固定機台的巡檢 min/max 原始觀測，N≥50 且研究條件、規格、分布均確認後，以 G 法報告 Pm／Pmk | 不接受出貨或 Excel 來源；只走研究核准，不建立生產界限或 OCAP |
| 完整時間診斷 | 以固定方法提出 A1、A2、B、C1、C2、C3、C4、D，保存 trend、Welch／Levene Holm、多峰與正式穩定性證據 | N<25 不可確認；B／C／D 只可人工理由確認為研究，不報 Cp／Cpk |
| 分布轉換 | 保存 Box-Cox、Johnson SU／SB／SL 四候選的參數、AD、尾端、單調性與 round-trip 證據 | 只允許人工理由確認已通過候選；原始分布接受時不自動推薦，仍保留完整候選證據 |

## 指數與參數

- G 法分位數使用 0.135%、50%、99.865% 分位數；常態模型下等價於六標準差寬度。
- 整體標準差採樣本標準差（`ddof=1`）；組內 `sigma_within` 只作變異估計與 Cw/Cwk 參考。
- 預設穩定性規則為：單點超界、連續 9 點同側、連續 6 點趨勢。規則 4 的 14 點交替接受兩種起始相位；規則 8 必須在中心線兩側且均位於 1σ 外。
- 分布最低樣本數為 20；分布顯著水準 `alpha=0.05`；X̄-S 逐點界限雙尾 `alpha=0.0027`。
- 目標值依特性重要度與樣本量調整；樣本不足時標示 preliminary／insufficient_sample，不把初步結果描述為已確效能力。

## 不可變研究與重建

研究版本保存：方法版本、程式版本、完整篩選、資料雜湊、規格快照、子組值、分布分析值、來源 ID、排除操作者／時間快照、圖表、逐點界限、I-MR 來源配對、兩圖穩定性、分布、時間模型、指標與適用性。時間模型確認會建立後繼版本並將原版標為 superseded，不覆寫原 JSON。ORM 與 PostgreSQL trigger 都禁止修改計算證據或刪除研究版本、樣本、界限與事件；只開放受控狀態轉換。送審與核准前會以相同轉接器重算來源雜湊；不一致時回 `409 STUDY_DATA_CHANGED`。

報表以 `study_version_id` 從保存樣本重建，驗證頁面來源與完整篩選，並直接輸出保存的變異 UCL／CL／LCL 及穩定性，不另行重算或混入目前原始資料。修改現在的來源資料後，由舊版本再次匯出的統計與界限必須不變。

## 黃金資料與容許誤差

`backend/tests/test_services/test_spc_golden.py` 與
`backend/scripts/spc_advanced_expected_2026_2.json` 固定涵蓋：

- X̄-S、X̄-R、I-MR 與不等 `n` 逐點界限；
- A1、A2、B、C3、D 候選；
- 單側與雙側規格；
- 位置穩定但變異失控；
- 無可接受分布時不回退、不產生 PPM／指標補值。
- p／np 精確離散界限與固定／不固定子組契約；
- N=60 的 Pm／Pmk 與 G 法三分位數；
- A1、A2、B、C1、C2、C3、C4、D 八類固定 raw datasets；
- Box-Cox、Johnson SU、Johnson SB、Johnson SL 四類固定 datasets。

黃金數值使用 `pytest.approx`；管制界限絕對容許差 `1e-8`，指數因對外顯示三位小數而使用 `1e-3`。資料雜湊、原因碼、圖表選型、狀態與 `null` 必須完全一致。任何 NaN／Infinity 均判定失敗。

進階 runner 不會由本次 actual 自動產生 expected。expected 是 committed、可審查的固定
JSON；每一個數值 path 都必須在 `tolerances` 明列 absolute／relative tolerance，缺少
tolerance 本身即 FAIL。執行結果含逐 path PASS／FAIL 差異，並可把 expected、actual、
tolerances、dataset/method/code version、結果及執行者保存至 `SPC軟體確效執行`。

## 重現步驟

從 repo 根目錄、使用專案 venv 執行：

```powershell
C:\QC_Database\venv\Scripts\python.exe -m pytest backend\tests\test_services\test_spc_golden.py -q
C:\QC_Database\venv\Scripts\python.exe backend\scripts\spc_regression.py
C:\QC_Database\venv\Scripts\python.exe backend\scripts\spc_advanced_regression.py
C:\QC_Database\venv\Scripts\python.exe backend\scripts\spc_advanced_regression.py --persist --executed-by <使用者ID>
```

第二個命令使用固定資料完成 JSON 保存／讀回，輸出方法版本、程式版本、SHA-256、圖表選型、每點界限、兩圖穩定性、分布、時間模型與指標。成功條件為 `[PASS]`，且無 NaN、無未說明的常態回退。

進階 runner 成功時最後一行必須精確為：

```text
[PASS] SPC 2026.2 進階分析確效通過；屬性圖、機器績效、時間模型與分布轉換皆符合固定基準。
```

2026-07-19 對正式 `qa_database` 執行 `--persist --executed-by 1` 已 PASS，保存
`SpcValidationRun.id=1`；dataset `spc-advanced-golden-2026.2`、method `2026.2`、
code `2026.1`、expected／actual／tolerances 均為 JSON object。此 ID 是該環境的
稽核證據，不是可跨環境假設的固定 ID。

完整發版驗證另包含：後端全量 pytest、兩個 regression runner、前端
lint/build/test、`npm audit`、`git diff --check`，以及依
[migration 38 runbook](migrations/38-spc-analysis-family-runbook.md) 執行 PostgreSQL
rollback dry-run、正式套用、idempotent 重跑與 schema/preflight 查核。

# Task 3：屬性研究版本、持續監控與版本報表

## 狀態

完成。attribute 已可透過既有研究 analyze/list/detail/history 生命週期保存不可變版本；machine 仍明確回傳 `SPC_ANALYSIS_FAMILY_NOT_IMPLEMENTED`。

## Commit

`功能：整合屬性研究版本與可追溯報表`

## 變更檔案

- `backend/services/spc_attribute_engine.py`：新增以 frozen center/alpha 計算 p／np 觀測值與逐點精確二項界限。
- `backend/services/spc_stability.py`：beyond-limits 採 raw count 精確離散界限；其餘規則採中心 0 的 Pearson residual。
- `backend/services/spc_study_service.py`：attribute dispatch、immutable x/n 樣本、retrospective/ongoing、family-isolated approval limits。
- `backend/services/spc_report.py`：僅由 saved version 產製 attribute workbook，含族別、interval、alpha、warnings、x/n 與核准 metadata。
- `backend/services/patrol_service.py`：移除即時計算 SPC 匯出路徑；含 SPC 的匯出必須由路由層建立或選取 immutable version。
- `backend/tests/test_services/test_spc_attribute_study.py`：新增 lifecycle、frozen ongoing、版本報表與 evidence 測試。
- `backend/tests/test_services/test_spc_study_service.py`、`test_spc_report_versioning.py`、`test_patrol.py`：將 2026.2 契約與 attribute 已支援行為納入既有回歸。

## RED / GREEN 證據

RED：

```powershell
& 'C:\QC_Database\venv\Scripts\python.exe' -m pytest backend\tests\test_services\test_spc_attribute_study.py -q
```

結果：`3 failed`；三項均因 `SpcStudyService.analyze()` 對 attribute 回傳 `SPC_ANALYSIS_FAMILY_NOT_IMPLEMENTED`。

另一次 evidence persistence RED：

```powershell
& 'C:\QC_Database\venv\Scripts\python.exe' -m pytest backend\tests\test_services\test_spc_attribute_study.py -q
```

結果：`1 failed, 2 passed`；缺少 `chart_result["eligibility_evidence"]`。

GREEN：

```powershell
& 'C:\QC_Database\venv\Scripts\python.exe' -m pytest backend\tests\test_services\test_spc_attribute_engine.py backend\tests\test_services\test_spc_attribute_adapter.py backend\tests\test_services\test_spc_stability.py backend\tests\test_spc_study_routes.py backend\tests\test_services\test_patrol.py backend\tests\test_services\test_spc_attribute_study.py backend\tests\test_services\test_spc_study_service.py backend\tests\test_services\test_spc_report_versioning.py -q
```

結果：`83 passed in 6.92s`。

```powershell
git diff --check
```

結果：exit 0。

## 自我審查與疑慮

- `SpcLimitVersion.limits` 是既有 JSON 快照欄位，足以保存 attribute 的 frozen center、alpha、interval、np baseline_n、rules 與離散界限；不需 schema migration。
- p 圖容許目前子組 n 改變，但每點都用 frozen p center/alpha 重算 exact count limits；np 圖會拒絕與 baseline n 不符的資料。
- attribute 的能力指標與 variable 的時間模型不適用，因此版本明確保存 unavailable reason；核准 gate 僅要求 attribute 圖可用且穩定，避免偽造 variable A1/A2 證據。
- Patrol 路由既有的 actor/permission/source/filter/version 驗證流程負責建立或選取版本；service 不再允許直接以 current data 產 SPC workbook。

## 後續修正：巡檢全段篩選正規化

UI 的 `position=全段` 已在 patrol export 路由轉為 canonical `pos=''`，建立版本與 `generate_version_report(... expected_filters=...)` 共用同一份 filters；維持既有 variable 預設，不自行改用 attribute 或補造 options。

RED：

```powershell
& 'C:\QC_Database\venv\Scripts\python.exe' -m pytest backend\tests\test_spc_study_routes.py::test_patrol_export_normalizes_full_position_before_creating_version -q
```

結果：`1 failed`，實際收到 `pos='全段'`。

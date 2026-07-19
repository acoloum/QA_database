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

## 審查修正：canonical options、監控證據與屬性報表

- attribute 選項統一為 `{interval, chart_type, alpha}`，預設為 `day/p/0.0027`；未知鍵、非物件、無效 interval/chart，以及 bool、字串、NaN、Inf 或不在 `(0, 1)` 的 alpha 都會拒絕。
- canonical options 同時供 adapter、資料雜湊、不可變版本與計算引擎使用。ongoing 省略 options 時，繼承 frozen limit options；顯式 options 任何 drift 都回 `SPC_ATTRIBUTE_OPTIONS_MISMATCH`。
- ongoing 版本報表由 `time_model_result.limit_version_id` 讀取實際核准界限與事件，版本稽核表明列監控界限 ID、limits、核准資訊、OCAP 與凍結狀態。
- attribute report 改為 p／np 專用 workbook，保留 x/n、逐點精確界限、Pearson residual 與單一圖表；continuous-variable 的能力、分布、時間模型與變異項目明確標示不適用與原因。
- attribute OCAP event 的 `observed_value` 保存 p 比例或 np count，`sample_id` 指向 immutable `[x, n]`，再由 `study_version_id + point_index` 重建 Pearson residual；`source_point_key` 保持原本穩定 identity。

RED：canonical options 初始測試因尚未提供 canonical helper/attribute adapter registry 而 ImportError；ongoing inherit 測試為 `1 failed`，省略 options 被 day 預設導致 interval mismatch；ongoing report evidence 測試為 `1 failed`，缺少監控界限 ID metadata；attribute OCAP 測試為 `1 failed`，observed value 為 null。

GREEN：

```powershell
& 'C:\QC_Database\venv\Scripts\python.exe' -m pytest backend\tests\test_services\test_spc_attribute_adapter.py backend\tests\test_services\test_spc_attribute_study.py backend\tests\test_spc_study_routes.py backend\tests\test_services\test_spc_report_versioning.py -q
```

結果：`29 passed in 6.03s`。

## 第二輪審查修正

- 新增 `spc_attribute_options.py`，adapter 與 service 共用 strict canonical options；legacy positional interval 同樣輸出完整 defaults 並納入 hash。
- 新增 immutable monitoring limit resolver，依 ongoing version 的 `limit_version_id` 以 eager load 取得 limit、baseline study 與 events，並驗證 family/stream/characteristic/source。
- route list/detail 預先批次取得 monitoring limits，避免 version serializer 對每筆 ongoing version 發出查詢。
- attribute event source key 現含 subgroup key 與排序 record membership 的 SHA-256 digest；display value 仍在 observed_value，x/n/residual 仍由 immutable sample/chart 關聯取得。

RED：adapter direct canonical test `1 failed`（只有 interval）；monitor resolver test ImportError（resolver 尚未存在）；membership test `1 failed`（變更 membership 仍被舊 source key dedup）。

## 最終審查修正：路由批次序列化

- `serialize_event` 改由 list/detail 建立的 version/sample maps 取得 immutable evidence，不再逐 event `session.get`。
- monitoring limits prefetch 後即以共用 ownership validator 驗證；缺失或 cross family/source/stream/characteristic pointer 回相同 SPC validation error。
- list/detail 會用一次批次版本查詢與一次批次 sample 查詢涵蓋 monitoring events，包括 baseline detail 指向其他 ongoing version 的事件。

## 補正：事件明細 immutable evidence

`GET /api/spc/events/<id>` 現在明確 preload event 的 study version/study 與 sample，並將 maps 交給 serializer；attribute response 可重建 x、n、display value、Pearson residual 與 subgroup key。

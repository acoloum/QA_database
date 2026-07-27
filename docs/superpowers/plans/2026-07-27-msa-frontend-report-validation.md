# MSA 工作台、報告與完整確效實作計畫

> **Required subskills:** 執行 UI 任務前使用 `frontend-design:frontend-design`，所有功能使用 `superpowers:test-driven-development`；產生與檢查正式 PDF 時使用 `pdf:pdf`；完成宣告前使用 `superpowers:verification-before-completion`。

**Goal:** 交付完整可用的 MSA 風險工作台、研究精靈、盲測收集、分層結果與核准體驗，並產生由不可變結果版本重建的 PDF／Excel 稽核報告，完成前後端、資料庫、報告與正式服務 smoke test。

**Architecture:** 前端沿用 React Router、React Query 與 Chart.js，但 MSA 圖表 model 留在 `components/msa/charts`，API 型別集中於 `types/msa.ts`。後端報告 service 只讀 `MsaResultVersion` 及其 frozen snapshots，不呼叫任何分析 engine。頁面依 method code 選擇證據面板；共同工作流、原始資料、設備／準則與稽核歷程不重複實作。

**Tech Stack:** React 19、TypeScript 5.9、React Router 7、TanStack React Query 5、Chart.js 4、React Bootstrap 2、Vitest 4、Testing Library、Flask 3.1、openpyxl 3.1.5、reportlab 4.2.5、Poppler。

**Global Constraints:**

- 前置依賴：[設備與準則基礎實作計畫](2026-07-27-msa-equipment-criteria-foundation.md) 與 [研究、統計與核准核心實作計畫](2026-07-27-msa-study-statistics-workflow.md) 必須完成。
- 依據已核准規格：[MSA 第四版完整模組設計](../specs/2026-07-27-msa-fourth-edition-module-design.md)。
- 首頁採已核准的「風險導向工作台」；結果頁採「分層證據」。
- 圖表、標籤、方法、狀態及錯誤都顯示人類可讀繁體中文，不只顯示內部 code。
- 顏色不是唯一狀態訊號；所有圖表有文字摘要或資料表。
- 報告只讀已保存結果；approved 才能沒有浮水印。
- 程式碼備註、錯誤訊息與 commit 訊息使用繁體中文。

---

## Task 1：建立只讀不可變結果的 Excel 報告

**Files:**

- Create: `backend/services/msa_report.py`
- Create: `backend/tests/test_services/test_msa_report.py`
- Modify: `backend/routes/msa.py`

### Step 1：先寫「來源改變不影響報告」失敗測試

```python
from openpyxl import load_workbook

from backend.services.msa_report import MsaReportService


def _sheet_values(workbook, sheet_name):
    return [
        tuple(cell.value for cell in row)
        for row in workbook[sheet_name].iter_rows()
    ]


def test_excel_rebuilds_only_from_saved_result_version(
    app, db_session, approved_msa_result,
):
    before = load_workbook(
        MsaReportService.generate_excel(approved_msa_result.id)
    )

    equipment_id = (
        approved_msa_result.raw_data_summary["plan_snapshot"]
        ["equipment_snapshot"][0]["equipment_id"]
    )
    equipment = MeasurementEquipment.query.get(equipment_id)
    equipment.name = "報告建立後更名的設備"
    db_session.commit()

    after = load_workbook(
        MsaReportService.generate_excel(approved_msa_result.id)
    )
    for sheet_name in before.sheetnames:
        assert _sheet_values(before, sheet_name) == _sheet_values(after, sheet_name)
```

### Step 2：先寫工作表與稽核欄位測試

```python
def test_excel_contains_auditable_sheets(approved_msa_result):
    workbook = load_workbook(
        MsaReportService.generate_excel(approved_msa_result.id),
        data_only=False,
    )
    assert workbook.sheetnames == [
        "研究摘要", "研究設計", "原始讀值", "統計結果",
        "圖表資料", "設備與校驗", "準則與判定", "核准歷程", "版本稽核",
    ]
    audit = dict(_sheet_values(workbook, "版本稽核"))
    assert audit["結果版本ID"] == approved_msa_result.id
    assert audit["資料雜湊"] == approved_msa_result.data_hash
    assert audit["方法代碼"] == approved_msa_result.method_code
    assert audit["方法版本"] == approved_msa_result.method_version
    assert audit["程式版本"] == approved_msa_result.code_version
```

另測：

- 所有方法都有對應統計明細。
- 原始讀值來自 `raw_data_summary` snapshot，不重新查有效觀測重算。
- 以 `= + - @` 開頭文字經公式注入防護。
- 圖表資料包含畫面使用的精確 series。
- 核准歷程有 actor/time/reason/separation check。
- draft/submitted/rejected 工作簿「研究摘要」有明顯 `草稿／未核准`。

### Step 3：執行測試，確認 service 尚不存在

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_report.py -q
```

Expected: collection FAIL。

### Step 4：建立報告 snapshot DTO

`MsaReportService._load_snapshot` 只可查：

- `MsaResultVersion`。
- result 關聯的 study identity。
- frozen plan snapshot。
- workflow decisions。

禁止呼叫：

- `MsaStudyService.analyze`。
- 任一 `analyze_*` 統計函式。
- 目前設備資格或目前準則。

```python
@staticmethod
def _load_snapshot(result_version_id: int) -> dict:
    result = MsaResultVersion.query.get(result_version_id)
    if result is None:
        raise MsaNotFound("MSA_RESULT_NOT_FOUND", "找不到 MSA 結果版本")
    return {
        "study": result.raw_data_summary["study_snapshot"],
        "plan": result.raw_data_summary["plan_snapshot"],
        "observations": result.raw_data_summary["observations"],
        "statistics": result.statistics,
        "charts": result.chart_data,
        "criteria": result.criteria_snapshot,
        "conclusion": result.conclusion,
        "workflow": serialize_report_decisions(result),
        "audit": serialize_result_audit(result),
    }
```

若目前 result 沒保存 `plan_snapshot` 或 observations，回 `MSA_REPORT_EVIDENCE_INCOMPLETE`，不可回頭重算。

### Step 5：產生 Excel

共用安全文字：

```python
def excel_safe(value):
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value
```

格式要求：

- freeze panes。
- filters。
- 可讀欄寬。
- 日期使用 ISO 8601。
- Decimal 不先轉顯示字串。
- 百分比使用 Excel number format。
- 圖表資料與圖表分開，圖表引用保存值。
- 不在 Excel 公式中重算正式指標。

### Step 6：接上 Excel route

```python
@msa_bp.get("/api/msa/results/<int:version_id>/report.xlsx")
@auth_required
@require_permission("msa.view")
@_handle_msa_errors
def download_msa_excel(current_user, version_id):
    output = MsaReportService.generate_excel(version_id)
    return send_file(
        output,
        as_attachment=True,
        download_name=f"MSA_{version_id}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
```

### Step 7：執行測試並提交

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_report.py backend\tests\test_msa_routes.py -q
```

Expected: PASS。

Commit:

```powershell
git add backend/services/msa_report.py backend/tests/test_services/test_msa_report.py backend/routes/msa.py
git commit -m "報表：建立 MSA 不可變 Excel 報告"
```

---

## Task 2：建立 PDF 報告、浮水印與 CJK 驗證

**Files:**

- Modify: `requirements.txt`
- Modify: `backend/services/msa_report.py`
- Modify: `backend/routes/msa.py`
- Modify: `backend/tests/test_services/test_msa_report.py`
- Create: `backend/tests/fixtures/fonts/README.md`

### Step 1：先寫 PDF metadata、浮水印與文字失敗測試

```python
from pypdf import PdfReader


def test_approved_pdf_has_no_draft_watermark(approved_msa_result):
    output = MsaReportService.generate_pdf(approved_msa_result.id)
    reader = PdfReader(output)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert approved_msa_result.study.study_no in text
    assert "未核准" not in text
    assert reader.metadata.title.startswith("MSA ")


def test_submitted_pdf_has_unapproved_watermark(submitted_msa_result):
    output = MsaReportService.generate_pdf(submitted_msa_result.id)
    text = "\n".join(
        page.extract_text() or "" for page in PdfReader(output).pages
    )
    assert "未核准" in text
```

另測：

- PDF 頁數 > 1 時每頁有 study no/result version/data hash 短碼。
- CJK 字型找到時繁體中文可抽取。
- 找不到 CJK 字型時正式模式回 `MSA_REPORT_FONT_MISSING`，不可輸出亂碼。
- 圖表取自 saved chart data。
- 各 method 的必要證據段落存在。

### Step 2：明確加入 reportlab 依賴

`requirements.txt` 加入目前已驗證版本：

```text
reportlab==4.2.5
pypdf==6.14.2
```

### Step 3：建立 CJK 字型解析

沿用既有 Windows/Linux 候選，但正式報告不 fallback Helvetica：

```python
CJK_FONT_CANDIDATES = (
    "C:/Windows/Fonts/msjh.ttc",
    "C:/Windows/Fonts/mingliu.ttc",
    "C:/Windows/Fonts/kaiu.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
)


def register_cjk_font() -> str:
    for path in CJK_FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("MSA-CJK", path))
                return "MSA-CJK"
            except Exception:
                continue
    raise MsaValidationError(
        "MSA_REPORT_FONT_MISSING",
        "伺服器缺少可用的繁體中文字型，無法產生正式 PDF",
    )
```

### Step 4：建立 PDF 結構

順序固定：

1. 封面與研究結論。
2. 研究設計與適用性。
3. 設備／校驗／解析度。
4. 原始資料摘要。
5. 方法統計證據。
6. 圖表。
7. 準則與三層判定。
8. 核准與稽核歷程。
9. 方法、程式、hash、產生時間。

page callback：

```python
def draw_page(canvas, doc):
    canvas.saveState()
    canvas.setFont(font_name, 7)
    canvas.drawString(15 * mm, 10 * mm, snapshot["study"]["study_no"])
    canvas.drawRightString(
        195 * mm,
        10 * mm,
        f"Result v{snapshot['audit']['result_version_no']} · "
        f"{snapshot['audit']['data_hash'][:12]} · {doc.page}",
    )
    if snapshot["audit"]["status"] != "approved":
        canvas.saveState()
        canvas.setFillAlpha(0.12)
        canvas.setFont(font_name, 42)
        canvas.rotate(35)
        canvas.drawCentredString(145 * mm, 25 * mm, "未核准")
        canvas.restoreState()
    canvas.restoreState()
```

### Step 5：接上 PDF route 並執行測試

```python
@msa_bp.get("/api/msa/results/<int:version_id>/report.pdf")
@auth_required
@require_permission("msa.view")
@_handle_msa_errors
def download_msa_pdf(current_user, version_id):
    output = MsaReportService.generate_pdf(version_id)
    return send_file(
        output,
        as_attachment=True,
        download_name=f"MSA_{version_id}.pdf",
        mimetype="application/pdf",
    )
```

Run:

```powershell
venv\Scripts\python.exe -m pytest backend\tests\test_services\test_msa_report.py backend\tests\test_msa_routes.py -q
```

Expected: PASS。

### Step 6：以 PDF skill 的 render 流程做視覺 QA

產生一份涵蓋長表格與至少兩張圖的測試 PDF，使用 Poppler render 全頁：

```powershell
venv\Scripts\python.exe backend\scripts\render_msa_fixture_report.py --output tmp\msa-report-qa.pdf
pdftoppm -png -r 144 tmp\msa-report-qa.pdf tmp\msa-report-page
```

逐頁確認：

- 繁體中文未變成方框。
- 表格不超出頁面。
- 標題未與頁首頁尾重疊。
- 浮水印不遮蔽內容。
- 圖例與軸標可讀。
- 分頁後表頭重複。

修正後重新 render，直到沒有可見排版瑕疵。`tmp` 輸出不提交。

### Step 7：提交

```powershell
git add requirements.txt backend/services/msa_report.py backend/routes/msa.py backend/tests/test_services/test_msa_report.py backend/tests/fixtures/fonts/README.md backend/scripts/render_msa_fixture_report.py
git commit -m "報表：完成 MSA PDF 與視覺驗證"
```

---

## Task 3：完成研究前端型別、hooks 與報告下載

**Files:**

- Modify: `src_frontend/src/types/msa.ts`
- Create: `src_frontend/src/hooks/useMsaStudies.ts`
- Test: `src_frontend/src/hooks/useMsaStudies.test.tsx`
- Modify: `src_frontend/src/utils/downloadFile.ts`

### Step 1：先寫查詢、狀態 mutation 與下載失敗測試

```typescript
it('分析時送出 frozen plan hash', async () => {
  vi.mocked(api.post).mockResolvedValueOnce({ data: { data: resultVersion } });
  const { result } = renderHook(() => useAnalyzeMsaPlan(), { wrapper });

  result.current.mutate({ planId: 7, expectedPlanHash: 'abc123' });

  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(api.post).toHaveBeenCalledWith('/msa/plans/7/analyze', {
    expected_plan_hash: 'abc123',
  });
});


it('核准時送出 expected status 與理由', async () => {
  vi.mocked(api.post).mockResolvedValueOnce({ data: { data: approvedResult } });
  const { result } = renderHook(() => useApproveMsaResult(), { wrapper });
  result.current.mutate({
    versionId: 12,
    expected_status: 'submitted',
    reason: '統計、設備與原始資料均已審查',
  });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(api.post).toHaveBeenCalledWith('/msa/results/12/approve', {
    expected_status: 'submitted',
    reason: '統計、設備與原始資料均已審查',
  });
});


it('下載已保存版本的 PDF', async () => {
  vi.mocked(api.get).mockResolvedValueOnce({ data: new Blob(['pdf']) });
  await downloadMsaReport(12, 'pdf', 'MSA-2026-0012');
  expect(api.get).toHaveBeenCalledWith('/msa/results/12/report.pdf', {
    responseType: 'blob',
  });
  expect(downloadResponseBlob).toHaveBeenCalledWith(
    expect.any(Blob),
    'MSA-2026-0012_v12.pdf',
    'application/pdf',
  );
});
```

### Step 2：建立完整 discriminated union

```typescript
export type MsaMethodCode =
  | 'MSA4_GRR_RANGE_1_0'
  | 'MSA4_GRR_XBAR_R_1_0'
  | 'MSA4_GRR_ANOVA_1_0'
  | 'MSA4_BIAS_1_0'
  | 'MSA4_LINEARITY_1_0'
  | 'MSA4_STABILITY_1_0'
  | 'MSA4_ATTRIBUTE_1_0'
  | 'MSA4_NONREPEATABLE_1_0';

export type MsaResult =
  | MsaGrrResult
  | MsaBiasResult
  | MsaLinearityResult
  | MsaStabilityResult
  | MsaAttributeResult
  | MsaNonrepeatableResult;
```

每個 result interface 以 `method_code` 作 discriminator；不得用 `Record<string, any>` 取代方法結果。

### Step 3：建立 hooks 與 query keys

新增：

- `useMsaDashboard`
- `useMsaStudies`
- `useMsaStudy`
- `useCreateMsaStudy`
- `useCreateMsaPlan`
- `useFreezeMsaPlan`
- `useMsaTasks`
- `useRecordMsaObservation`
- `usePreviewMsaObservationImport`
- `useConfirmMsaObservationImport`
- `useValidateMsaPlan`
- `useAnalyzeMsaPlan`
- `useSubmitMsaResult`
- `useApproveMsaResult`
- `useRejectMsaResult`
- `useVoidMsaResult`
- `useMsaHistory`
- `downloadMsaReport`

所有 mutation 只 invalidate 受影響的 study/dashboard/list key。

### Step 4：執行 hooks 測試並提交

Run:

```powershell
cd src_frontend
npx vitest run src/hooks/useMsaStudies.test.tsx
```

Expected: PASS。

Commit:

```powershell
git add src_frontend/src/types/msa.ts src_frontend/src/hooks/useMsaStudies.ts src_frontend/src/hooks/useMsaStudies.test.tsx src_frontend/src/utils/downloadFile.ts
git commit -m "功能：完成 MSA 研究前端資料層"
```

---

## Task 4：建立 MSA 視覺系統與風險導向工作台

**Files:**

- Create: `src_frontend/src/pages/msa/msa.css`
- Modify: `src_frontend/src/pages/msa/MsaWorkspacePage.tsx`
- Create: `src_frontend/src/components/msa/MsaRiskCard.tsx`
- Create: `src_frontend/src/components/msa/MsaWorkQueue.tsx`
- Test: `src_frontend/src/pages/msa/MsaWorkspacePage.test.tsx`

### Step 1：先寫風險排序與可存取性失敗測試

```typescript
it('依阻擋風險優先呈現工作，而不是只顯示總數', async () => {
  render(<MsaWorkspacePage />);

  const queues = await screen.findAllByTestId('msa-work-item');
  expect(queues[0]).toHaveTextContent('校驗失敗');
  expect(queues[1]).toHaveTextContent('待核准');
  expect(queues[2]).toHaveTextContent('再研究逾期');
});


it('狀態同時提供圖示與文字', async () => {
  render(<MsaWorkspacePage />);
  const item = await screen.findByText('校驗逾期 3 件');
  expect(item.closest('[data-severity]')).toHaveAttribute('data-severity', 'critical');
  expect(item.closest('[data-severity]')).toHaveAccessibleName(/重大風險/);
});
```

另測 loading、empty、API error、無 `msa.manage` 時隱藏管理捷徑、鍵盤可到達全部卡片。

### Step 2：定義視覺語言

在 `msa.css` 以 MSA namespace 隔離：

```css
.msa-shell {
  --msa-ink: #172126;
  --msa-muted: #617078;
  --msa-surface: #f7f4ee;
  --msa-panel: #fffdfa;
  --msa-line: #d8d2c6;
  --msa-accent: #0f6b62;
  --msa-warning: #a55f05;
  --msa-danger: #a8342f;
  --msa-info: #285a8e;
  color: var(--msa-ink);
  background:
    radial-gradient(circle at 90% 0%, rgba(15, 107, 98, 0.09), transparent 30rem),
    var(--msa-surface);
}
```

排版：

- 頁面標題採現有系統字體，不引入外部網路字型。
- 統計數值使用 tabular numerals。
- panel 用細邊框與小陰影，不使用大量膠囊或同質卡片。
- 重大風險保留高對比紅；正常狀態用墨綠。

### Step 3：建立工作台資訊架構

頂部：

- 我的研究工作。
- 待核准。
- 設備阻擋。
- 再研究逾期。

中部主欄：

- 依 severity/source date 排序的工作佇列。
- 每筆顯示原因、影響研究／設備、責任人、期限與下一步。

側欄：

- 建立研究。
- 設備清單。
- 判定準則。
- 匯入歷程。
- 確效執行狀態。

### Step 4：執行元件測試與視覺檢查

Run:

```powershell
cd src_frontend
npx vitest run src/pages/msa/MsaWorkspacePage.test.tsx
npm run dev
```

使用瀏覽器在 1440×900、1024×768、390×844 檢查：

- 重要工作首屏可見。
- 卡片不橫向溢出。
- 文字縮放 200% 仍可操作。
- focus ring 可見。
- 不依 hover 才顯示必要資訊。

### Step 5：提交

```powershell
git add src_frontend/src/pages/msa/msa.css src_frontend/src/pages/msa/MsaWorkspacePage.tsx src_frontend/src/components/msa/MsaRiskCard.tsx src_frontend/src/components/msa/MsaWorkQueue.tsx src_frontend/src/pages/msa/MsaWorkspacePage.test.tsx
git commit -m "介面：建立 MSA 風險導向工作台"
```

---

## Task 5：完成研究清單與方法導向研究精靈

**Files:**

- Create: `src_frontend/src/pages/msa/MsaStudyListPage.tsx`
- Create: `src_frontend/src/pages/msa/MsaStudyWizardPage.tsx`
- Create: `src_frontend/src/components/msa/MsaMethodSelector.tsx`
- Create: `src_frontend/src/components/msa/MsaPlanReview.tsx`
- Modify: `src_frontend/src/App.tsx`
- Test: `src_frontend/src/pages/msa/MsaStudyWizardPage.test.tsx`
- Test: `src_frontend/src/pages/msa/MsaStudyListPage.test.tsx`

### Step 1：先寫方法選擇與 freeze 阻擋失敗測試

```typescript
it('偏倚研究要求可追溯參考值後才能進入檢閱', async () => {
  const user = userEvent.setup();
  render(<MsaStudyWizardPage />);

  await user.click(screen.getByRole('radio', { name: '偏倚' }));
  await user.click(screen.getByRole('button', { name: '下一步' }));

  expect(screen.getByRole('alert')).toHaveTextContent('需要可追溯參考值或參考標準');
});


it('設備逾期時明確阻擋凍結且顯示設備編號', async () => {
  render(<MsaPlanReview />);
  expect(await screen.findByText('EQ-017 校驗已逾期')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '凍結研究計畫' })).toBeDisabled();
});
```

另測：

- Xbar-R 建議 10 parts/3 appraisers/2–3 trials，但允許受控調整。
- attribute 顯示 categories、truth、灰色區設定。
- nonrepeatable 強制四項物理假設。
- 同一步驟錯誤摘要可點擊跳到欄位。
- 往返步驟不遺失輸入。
- 提交重複時按鈕 disabled。

### Step 2：建立方法比較卡

每個方法顯示：

- 適用情境。
- 最低資料需求。
- 可回答的問題。
- 不能回答的問題。
- 所需設備／參考標準。

例如 Range 必須標示「快速篩選，不分解完整 EV/AV/PV」。

### Step 3：建立六步精靈

1. 研究目的與方法。
2. 品質特性、規格、顧客／產品。
3. 設備、參考標準與解析度。
4. 零件、評價人、試驗與物理假設。
5. 判定準則。
6. 隨機順序、snapshot 與 freeze 檢閱。

`MsaPlanReview` 顯示後端 validate 回應，不在前端自行判斷正式資格。

### Step 4：建立清單

篩選：

- 我的／全部。
- method。
- status。
- conclusion。
- due/restudy state。
- customer/product/characteristic。

預設排序：

1. submitted 待核准。
2. due/overdue。
3. collecting。
4. 最近更新。

### Step 5：加入路由

```tsx
<Route path="/msa/studies" element={<MsaStudyListPage />} />
<Route path="/msa/studies/new" element={<MsaStudyWizardPage />} />
<Route path="/msa/studies/:studyId/edit" element={<MsaStudyWizardPage />} />
```

### Step 6：執行測試並提交

Run:

```powershell
cd src_frontend
npx vitest run src/pages/msa/MsaStudyWizardPage.test.tsx src/pages/msa/MsaStudyListPage.test.tsx src/App.test.tsx
```

Expected: PASS。

Commit:

```powershell
git add src_frontend/src/pages/msa/MsaStudyListPage.tsx src_frontend/src/pages/msa/MsaStudyWizardPage.tsx src_frontend/src/components/msa/MsaMethodSelector.tsx src_frontend/src/components/msa/MsaPlanReview.tsx src_frontend/src/App.tsx src_frontend/src/pages/msa/MsaStudyWizardPage.test.tsx src_frontend/src/pages/msa/MsaStudyListPage.test.tsx
git commit -m "介面：完成 MSA 研究清單與精靈"
```

---

## Task 6：完成逐筆盲測、管理矩陣與 Excel 匯入

**Files:**

- Create: `src_frontend/src/pages/msa/MsaDataCollectionPage.tsx`
- Create: `src_frontend/src/components/msa/MsaBlindEntry.tsx`
- Create: `src_frontend/src/components/msa/MsaObservationMatrix.tsx`
- Create: `src_frontend/src/components/msa/MsaObservationImportReview.tsx`
- Modify: `src_frontend/src/App.tsx`
- Test: `src_frontend/src/pages/msa/MsaDataCollectionPage.test.tsx`

### Step 1：先寫盲測不洩漏與修正失敗測試

```typescript
it('評價人只看到盲碼與目前量測欄位', async () => {
  render(<MsaDataCollectionPage />);
  expect(await screen.findByText('盲碼 P-07')).toBeInTheDocument();
  expect(screen.queryByText('真實零件 LOT-A-001')).not.toBeInTheDocument();
  expect(screen.queryByText('參考值 10.000')).not.toBeInTheDocument();
  expect(screen.queryByText('前次讀值 10.003')).not.toBeInTheDocument();
});


it('修正讀值必須填寫理由並建立後繼紀錄', async () => {
  const user = userEvent.setup();
  render(<MsaObservationMatrix />);
  await user.click(await screen.findByRole('button', { name: '修正 P-07 第 1 次' }));
  await user.clear(screen.getByLabelText('新讀值'));
  await user.type(screen.getByLabelText('新讀值'), '10.002');
  await user.click(screen.getByRole('button', { name: '確認修正' }));
  expect(screen.getByRole('alert')).toHaveTextContent('請填寫修正理由');
});
```

另測：

- Enter 送出後焦點移到下一 task。
- 送出中不能連點。
- API conflict 顯示最新 task 狀態。
- 矩陣只對 `msa.manage` 顯示。
- 匯入問題顯示 sheet/cell/code。
- 計數型以可存取 radio/button group 輸入。
- 進度顯示完成／總數，不只百分比。

### Step 2：實作盲測輸入

畫面只用後端 tasks DTO，不從 study detail 拼真實 part：

```tsx
<form onSubmit={handleSubmit}>
  <p className="msa-eyebrow">量測 {task.requested_order} / {task.total_tasks}</p>
  <h1>盲碼 {task.blind_code}</h1>
  <MeasurementInput method={task.value_type} unit={task.unit} />
  <button type="submit" disabled={record.isPending}>儲存並前往下一件</button>
</form>
```

### Step 3：實作管理矩陣與修正歷程

- cell 顯示 current value、source、entered by/time。
- corrected cell 顯示 history icon。
- 點擊展開 original → successor chain。
- 無權限者不得看到矩陣路由內容。

### Step 4：實作 Excel 預覽檢閱

顯示：

- 欄位 mapping。
- valid/warning/blocking counts。
- 每個 cell issue。
- 解決後 confirm。
- confirm 後 server counts 與 batch hash。

不得在前端重新解析 Excel 作正式判定；前端可顯示檔名與大小，解析結果以後端為準。

### Step 5：加入路由、測試與提交

```tsx
<Route path="/msa/studies/:studyId/collect" element={<MsaDataCollectionPage />} />
```

Run:

```powershell
cd src_frontend
npx vitest run src/pages/msa/MsaDataCollectionPage.test.tsx
```

Expected: PASS。

Commit:

```powershell
git add src_frontend/src/pages/msa/MsaDataCollectionPage.tsx src_frontend/src/components/msa/MsaBlindEntry.tsx src_frontend/src/components/msa/MsaObservationMatrix.tsx src_frontend/src/components/msa/MsaObservationImportReview.tsx src_frontend/src/App.tsx src_frontend/src/pages/msa/MsaDataCollectionPage.test.tsx
git commit -m "介面：完成 MSA 盲測資料收集"
```

---

## Task 7：建立方法圖表 models 與資料表替代

**Files:**

- Create: `src_frontend/src/components/msa/charts/msaChartModels.ts`
- Create: `src_frontend/src/components/msa/charts/MsaGrrCharts.tsx`
- Create: `src_frontend/src/components/msa/charts/MsaBiasLinearityCharts.tsx`
- Create: `src_frontend/src/components/msa/charts/MsaStabilityCharts.tsx`
- Create: `src_frontend/src/components/msa/charts/MsaAttributeCharts.tsx`
- Create: `src_frontend/src/components/msa/charts/MsaNonrepeatableCharts.tsx`
- Test: `src_frontend/src/components/msa/charts/msaChartModels.test.ts`

### Step 1：先寫純 model 失敗測試

```typescript
it('GRR 變差圖顯示人類可讀中文，不暴露內部代碼', () => {
  const model = buildGrrVariationModel(grrResult);
  expect(model.data.labels).toEqual(['重複性 EV', '再現性 AV', '量具 GRR', '零件間 PV']);
  expect(model.summary).toContain('量具 GRR 佔研究變差');
  expect(JSON.stringify(model)).not.toContain('ev_sigma');
});


it('線性圖包含零偏倚線、回歸線與信賴帶', () => {
  const model = buildLinearityModel(linearityResult);
  expect(model.data.datasets.map(dataset => dataset.label)).toEqual(
    expect.arrayContaining(['個別偏倚', '平均偏倚', '回歸線', '零偏倚', '95% 信賴帶'])
  );
});
```

另測：

- stability 違規點有 rule text。
- attribute confusion matrix 行列總和正確。
- unavailable 指標不畫 0。
- nonrepeatable 顯示配對線與差值分布。
- 每個 chart model 產生 text summary/table rows。

### Step 2：建立共用圖表可存取契約

```typescript
export interface AccessibleMsaChartModel {
  title: string;
  summary: string;
  data: ChartData;
  options: ChartOptions;
  table: {
    columns: { key: string; label: string }[];
    rows: Record<string, string | number | null>[];
  };
}
```

元件提供：

- Canvas chart。
- 同步文字摘要。
- 「顯示資料表」按鈕。
- 可下載 CSV 的 saved chart data。

### Step 3：建立方法圖表

GRR：

- Xbar/R。
- part/appraiser interaction。
- variation component。
- by-part/by-appraiser distribution。

Bias/Linearity：

- bias CI。
- individual/mean bias、regression、zero、CI/prediction band。
- residual plot。

Stability：

- Xbar-R/Xbar-S/I-MR。
- event markers 與 rule violations。

Attribute：

- confusion matrix。
- appraiser agreement。
- gray-zone strata。

Nonrepeatable：

- paired/split lines。
- difference distribution。
- station/nested component。

### Step 4：執行測試並提交

Run:

```powershell
cd src_frontend
npx vitest run src/components/msa/charts/msaChartModels.test.ts
```

Expected: PASS。

Commit:

```powershell
git add src_frontend/src/components/msa/charts/msaChartModels.ts src_frontend/src/components/msa/charts/MsaGrrCharts.tsx src_frontend/src/components/msa/charts/MsaBiasLinearityCharts.tsx src_frontend/src/components/msa/charts/MsaStabilityCharts.tsx src_frontend/src/components/msa/charts/MsaAttributeCharts.tsx src_frontend/src/components/msa/charts/MsaNonrepeatableCharts.tsx src_frontend/src/components/msa/charts/msaChartModels.test.ts
git commit -m "介面：建立 MSA 方法圖表與可存取資料表"
```

---

## Task 8：完成分層證據結果頁

**Files:**

- Create: `src_frontend/src/pages/msa/MsaResultPage.tsx`
- Create: `src_frontend/src/components/msa/MsaResultHero.tsx`
- Create: `src_frontend/src/components/msa/MsaEvidenceLayers.tsx`
- Create: `src_frontend/src/components/msa/MsaMethodEvidence.tsx`
- Create: `src_frontend/src/components/msa/MsaAuditEvidence.tsx`
- Modify: `src_frontend/src/App.tsx`
- Test: `src_frontend/src/pages/msa/MsaResultPage.test.tsx`

### Step 1：先寫三層判定與證據失敗測試

```typescript
it('分開顯示統計結果、系統判定與工程判斷', async () => {
  render(<MsaResultPage />);
  expect(await screen.findByRole('heading', { name: '統計結果' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: '系統判定' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: '工程判斷與處置' })).toBeInTheDocument();
  expect(screen.getByText('%GRR 12.4%')).toBeInTheDocument();
  expect(screen.getByText('條件接受')).toBeInTheDocument();
});


it('顯示方法、程式、資料與準則版本', async () => {
  render(<MsaResultPage />);
  expect(await screen.findByText('MSA4_GRR_ANOVA_1_0')).toBeInTheDocument();
  expect(screen.getByText(/資料雜湊 abc123/)).toBeInTheDocument();
  expect(screen.getByText(/準則 v3/)).toBeInTheDocument();
});
```

另測：

- conditional 缺 action 顯示送審 blocker。
- unavailable 指標顯示原因，不顯示 `0.00`。
- 原始變差分量與調整值並列。
- ANOVA full/reduced 皆可查看。
- warnings/blockers 首屏可達。
- 資料表在 chart canvas 不可用時仍存在。

### Step 2：建立結果首屏

首屏固定呈現：

- 結論狀態與明確文字。
- 主要指標。
- 阻擋／警告。
- 方法／結果版本／資料 hash。
- 下一個合法動作。

不得把完整結果塞成等權重小卡。

### Step 3：建立四層證據導覽

1. `結論`：統計、系統、工程判斷。
2. `方法證據`：ANOVA table、變差分量、CI、Kappa、regression 等。
3. `圖表與原始資料`：saved chart data、observations、修正鏈。
4. `設備、準則與稽核`：設備校驗 snapshot、criteria snapshot、workflow。

### Step 4：以 method discriminator 選擇面板

```tsx
switch (result.method_code) {
  case 'MSA4_GRR_RANGE_1_0':
  case 'MSA4_GRR_XBAR_R_1_0':
  case 'MSA4_GRR_ANOVA_1_0':
    return <MsaGrrEvidence result={result} />;
  case 'MSA4_BIAS_1_0':
  case 'MSA4_LINEARITY_1_0':
    return <MsaBiasLinearityEvidence result={result} />;
  case 'MSA4_STABILITY_1_0':
    return <MsaStabilityEvidence result={result} />;
  case 'MSA4_ATTRIBUTE_1_0':
    return <MsaAttributeEvidence result={result} />;
  case 'MSA4_NONREPEATABLE_1_0':
    return <MsaNonrepeatableEvidence result={result} />;
}
```

TypeScript 必須用 exhaustive `never` guard，新增方法時 compile fail。

### Step 5：加入路由、測試與提交

```tsx
<Route path="/msa/results/:versionId" element={<MsaResultPage />} />
```

Run:

```powershell
cd src_frontend
npx vitest run src/pages/msa/MsaResultPage.test.tsx
```

Expected: PASS。

Commit:

```powershell
git add src_frontend/src/pages/msa/MsaResultPage.tsx src_frontend/src/components/msa/MsaResultHero.tsx src_frontend/src/components/msa/MsaEvidenceLayers.tsx src_frontend/src/components/msa/MsaMethodEvidence.tsx src_frontend/src/components/msa/MsaAuditEvidence.tsx src_frontend/src/App.tsx src_frontend/src/pages/msa/MsaResultPage.test.tsx
git commit -m "介面：完成 MSA 分層證據結果頁"
```

---

## Task 9：完成送審、核准、退回、作廢與報告下載體驗

**Files:**

- Create: `src_frontend/src/components/msa/MsaWorkflowBar.tsx`
- Create: `src_frontend/src/components/msa/MsaDecisionModal.tsx`
- Create: `src_frontend/src/components/msa/MsaHistoryDrawer.tsx`
- Modify: `src_frontend/src/pages/msa/MsaResultPage.tsx`
- Test: `src_frontend/src/components/msa/MsaWorkflowBar.test.tsx`
- Test: `src_frontend/src/components/msa/MsaDecisionModal.test.tsx`

### Step 1：先寫權限、自己核准錯誤與下載失敗測試

```typescript
it('管理者可送審但沒有核准按鈕', () => {
  authMock.mockReturnValue({
    hasPermission: (permission: string) => permission === 'msa.manage',
  });
  render(<MsaWorkflowBar result={analyzedResult} />);
  expect(screen.getByRole('button', { name: '送審' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '核准' })).not.toBeInTheDocument();
});


it('自己核准遭拒時顯示服務端職責分離原因', async () => {
  approveMock.mockRejectedValueOnce({
    response: {
      data: {
        error: {
          code: 'MSA_SELF_APPROVAL_FORBIDDEN',
          message: '建立、執行或輸入本研究資料的人員不得核准本研究',
        },
      },
    },
  });
  const user = userEvent.setup();
  render(<MsaDecisionModal action="approve" result={submittedResult} />);
  await user.type(screen.getByLabelText('核准理由'), '已完成審查');
  await user.click(screen.getByRole('button', { name: '確認核准' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('不得核准本研究');
});
```

另測：

- conditional 送審需措施與期限。
- reject/void 理由必填。
- conflict 顯示「狀態已更新」並重新 fetch。
- 未核准 PDF 下載按鈕標示「含未核准浮水印」。
- approved PDF 標示「正式報告」。
- history 顯示 separation check。

### Step 2：建立工作流 action map

```typescript
const actionConfig = {
  submit: { permission: 'msa.manage', label: '送審', expectedStatus: 'analyzed' },
  approve: { permission: 'msa.approve', label: '核准', expectedStatus: 'submitted' },
  reject: { permission: 'msa.approve', label: '退回', expectedStatus: 'submitted' },
  void: { permission: 'msa.approve', label: '作廢', expectedStatus: 'approved' },
} as const;
```

前端可隱藏無權限 action，但服務端仍是唯一授權來源。

### Step 3：建立決策 modal

- 顯示 result version/hash。
- 顯示 expected status。
- 理由必填。
- conditional 顯示 action rows 與 due date。
- 核准前 checkbox：已檢查統計、圖表、原始讀值、設備校驗、準則與職責分離。
- 不能用 checkbox 繞過服務端資格。

### Step 4：建立歷程與下載

歷程按時間顯示：

- plan freeze。
- data corrections。
- analysis versions。
- submit/approve/reject/void/supersede。
- restudy link。

下載按鈕直接用 result version id，不用 study current result。

### Step 5：執行測試並提交

Run:

```powershell
cd src_frontend
npx vitest run src/components/msa/MsaWorkflowBar.test.tsx src/components/msa/MsaDecisionModal.test.tsx src/pages/msa/MsaResultPage.test.tsx
```

Expected: PASS。

Commit:

```powershell
git add src_frontend/src/components/msa/MsaWorkflowBar.tsx src_frontend/src/components/msa/MsaDecisionModal.tsx src_frontend/src/components/msa/MsaHistoryDrawer.tsx src_frontend/src/pages/msa/MsaResultPage.tsx src_frontend/src/components/msa/MsaWorkflowBar.test.tsx src_frontend/src/components/msa/MsaDecisionModal.test.tsx
git commit -m "介面：完成 MSA 核准歷程與報告下載"
```

---

## Task 10：前端完整回歸、可存取性與 build 驗證

**Files:**

- Modify only files required by failures; do not perform unrelated cleanup.

### Step 1：執行 MSA 前端測試

Run:

```powershell
cd src_frontend
npx vitest run src/hooks/useMsaEquipment.test.tsx src/hooks/useMsaImports.test.tsx src/hooks/useMsaCriteria.test.tsx src/hooks/useMsaStudies.test.tsx src/pages/msa/MsaWorkspacePage.test.tsx src/pages/msa/MeasurementEquipmentPage.test.tsx src/components/msa/EquipmentImportReview.test.tsx src/pages/msa/MsaCriteriaPage.test.tsx src/pages/msa/MsaStudyListPage.test.tsx src/pages/msa/MsaStudyWizardPage.test.tsx src/pages/msa/MsaDataCollectionPage.test.tsx src/components/msa/charts/msaChartModels.test.ts src/pages/msa/MsaResultPage.test.tsx src/components/msa/MsaWorkflowBar.test.tsx src/components/msa/MsaDecisionModal.test.tsx src/components/Sidebar.test.tsx src/App.test.tsx
```

Expected: PASS。

### Step 2：執行全前端回歸

Run:

```powershell
cd src_frontend
npm test -- --run
npm run lint
npm run build
npm audit
```

Expected:

- tests PASS。
- lint 無 error。
- build 成功。
- audit 結果逐項記錄；若有可利用漏洞，依風險修正並重跑，不以強制 major upgrade 破壞專案。

### Step 3：瀏覽器視覺／互動 smoke

在開發或隔離測試資料環境驗證：

- `/msa`
- `/msa/equipment`
- `/msa/imports`
- `/msa/criteria`
- `/msa/studies`
- `/msa/studies/new`
- `/msa/studies/:id/collect`
- `/msa/results/:id`

每頁檢查：

- 1440×900、1024×768、390×844。
- keyboard-only。
- 200% zoom。
- loading/empty/error。
- 權限邊界。
- 圖表資料表替代。
- 無 console error。

### Step 4：若有修正，提交

先以 `git diff --name-only` 確認變更，再逐一 `git add` 本任務實際修正的 MSA 前端檔案；不得使用 `git add .`。有修正時提交 `修正：完成 MSA 前端整合驗證`，無修正則不建立空 commit。

---

## Task 11：正式資料庫、Authenticated API 與報告 smoke

**Files:**

- Create: `backend/scripts/smoke_msa.py`
- Create: `docs/runbooks/msa-production-smoke.md`

### Step 1：建立可清理的 smoke runner

runner 必須：

1. 使用環境提供的測試管理／執行／核准三個帳號或 token。
2. 建立格式為 `SMOKE-MSA-20260727T153000` 的 timestamp 前綴設備與準則。
3. 建立最小 GRR 研究。
4. freeze plan。
5. 輸入完整 observations。
6. analyze。
7. manager submit。
8. 確認 executor 自己 approve 回 403 `MSA_SELF_APPROVAL_FORBIDDEN`。
9. 獨立 approver approve。
10. 下載 PDF/Excel，驗證 magic bytes、非空、hash 欄位。
11. 清理可刪除的 smoke records；不可變 evidence 依 runbook 標記 void/test tenant，不直接刪除。

不得把 production secrets 寫入腳本或 commit。

### Step 2：重啟實際服務後再 smoke

先依正式部署方式重啟 Flask/Waitress，使新 ORM 與 Blueprint 生效。確認 listener：

```powershell
Get-NetTCPConnection -LocalPort 5001 -State Listen
```

再執行：

```powershell
venv\Scripts\python.exe -m backend.scripts.smoke_msa --base-url http://localhost:5001
```

如果正式入口是 Nginx，另驗證：

```powershell
venv\Scripts\python.exe -m backend.scripts.smoke_msa --base-url http://localhost:8080
```

不可在未啟動實際服務時宣稱 live UI/API 已驗證。

### Step 3：驗證資料庫限制

在測試交易或專用 smoke database：

- 重複設備編號被 UNIQUE 阻擋。
- approved calibration UPDATE/DELETE 被 trigger 阻擋。
- frozen plan UPDATE 被阻擋。
- observation UPDATE/DELETE 被阻擋。
- result UPDATE/DELETE 被阻擋。
- 同研究兩個 submitted result 被 partial unique 阻擋。

### Step 4：驗證報告

- PDF 用 Poppler render 全頁並抽取文字。
- Excel 用 openpyxl 讀取全部 sheet。
- source master 改變後同 result version 的報告值不變。
- approved 無浮水印；submitted 有未核准浮水印。
- 每份都有 method/code/data/criteria/result version。

### Step 5：提交 runbook 與 runner

```powershell
git add backend/scripts/smoke_msa.py docs/runbooks/msa-production-smoke.md
git commit -m "驗證：建立 MSA 正式服務 smoke 流程"
```

---

## Task 12：全專案最終驗證與交付

**Files:**

- Modify only files required by verified failures.

### Step 1：執行後端全測試

```powershell
venv\Scripts\python.exe -m pytest backend\tests -q
```

Expected: PASS。

### Step 2：執行前端全測試與靜態檢查

```powershell
cd src_frontend
npm test -- --run
npm run lint
npm run build
```

Expected: PASS。

### Step 3：執行統計確效

```powershell
venv\Scripts\python.exe -m backend.scripts.run_msa_validation --all
```

Expected: 所有 golden case PASS；每次執行已持久化。

### Step 4：執行格式與變更邊界檢查

```powershell
git diff --check
git status --short
git diff -- src_frontend/vite.config.ts
```

Expected:

- 無 whitespace error。
- 所有 MSA 變更已提交。
- 使用者既有 `src_frontend/vite.config.ts` 變更未被納入 MSA commit。

### Step 5：確認 migration 與正式 smoke 證據

記錄：

- migration 44/45/46 已套用的資料庫與時間。
- 實際服務 PID/listener。
- authenticated API smoke 結果。
- self-approval 403 證據。
- PDF/Excel 檔案 hash 與視覺 QA。
- golden validation run IDs。

### Step 6：若最終驗證產生修正，單獨提交並重跑全部檢查

先以 `git diff --name-only` 確認變更，再逐一 `git add` 最終驗證實際修正的 MSA 檔案；不得使用 `git add .`。有修正時提交 `修正：完成 MSA 全系統確效` 並重跑全部檢查；若沒有修正，不建立空 commit。

---

## 本計畫完成條件

- 工作台依風險與下一步排序，不只是 KPI 卡片集合。
- 研究精靈依方法動態要求設備、參考標準、設計與物理假設。
- 評價人頁不洩漏真實零件、參考值、前次讀值或他人讀值。
- 結果頁分開呈現統計、系統判定、工程判斷及四層證據。
- 所有方法圖表都有文字摘要與資料表替代。
- 核准、退回、作廢及報告下載均鎖定 result version 與 expected status。
- Excel/PDF 只從 saved result snapshot 重建；未核准 PDF 有浮水印。
- PDF 已逐頁 render 視覺驗證；Excel 已重新開啟驗證。
- 前後端全測試、lint、build、golden validation、資料庫限制與 authenticated smoke 全部通過。
- 正式回報清楚區分 code test、DB constraint test、API smoke 與 live browser 驗證。

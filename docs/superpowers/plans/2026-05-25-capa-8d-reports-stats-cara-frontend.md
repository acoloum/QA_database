# CAPA 8D 報表 + 客訴統計 + CARA 前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 QMS 系統的 AIAG 8D 報表匯出（PDF+Excel）、客訴統計圖表頁、CARA 前端重寫，使其對接新版後端 API。

**Architecture:**
- 後端報表由 openpyxl（Excel）與 reportlab（PDF）產生，透過 Flask `send_file` 回傳二進位流。
- 前端匯出按鈕呼叫報表端點，以 `blob` 下載；客訴統計頁使用已存在的 `useComplaintStats*` hooks + Chart.js (react-chartjs-2)。
- CARA 前端重寫：建立 `useCARA.ts` hook，重寫 CARAModal 對接 `/api/caras/*` 新版端點。

**Tech Stack:** Flask + openpyxl + reportlab, React 19 + TypeScript + react-chartjs-2 + react-bootstrap

---

## 狀態確認（已完成，不需要做）

- CAPAModal D0-D8 完整流程（含 5Why、FishboneEditor 表格、D7 橫展）✅
- NCMR 頁面的「開立 CAPA」按鈕 ✅
- 客訴頁面的「開立 CAPA」按鈕 ✅
- 後端 CAPA 所有 CRUD 與 gate 端點 ✅
- 後端 CARA 新版 API（/api/caras/*）✅

---

## 檔案結構

**新增：**
- `backend/services/eightd_excel.py` — Excel 8D 報表服務
- `backend/services/eightd_pdf.py` — PDF 8D 報表服務
- `src_frontend/src/pages/complaint/ComplaintStatsPage.tsx` — 客訴統計圖表頁
- `src_frontend/src/hooks/useCARA.ts` — CARA React Query hooks

**修改：**
- `backend/routes/capa.py:165-177` — 完成 PDF/Excel 路由（目前回 501）
- `src_frontend/src/hooks/useCapa.ts` — 加入 `useExport8DPdf` / `useExport8DExcel`
- `src_frontend/src/components/capa/CAPAModal.tsx` — 加入匯出按鈕（Modal.Footer）
- `src_frontend/src/components/cara/CARAModal.tsx` — 重寫對接新 API
- `src_frontend/src/App.tsx` — 加入 `/complaints/stats` 路由
- `src_frontend/src/components/common/Sidebar.tsx`（或 MainLayout）— 加入統計連結

---

## Task 1: 安裝 reportlab 並建立 8D Excel 報表服務

**Files:**
- Create: `backend/services/eightd_excel.py`

- [ ] **Step 1: 在 venv 安裝 reportlab**

```bash
cd C:/QC_Database
./venv/Scripts/pip install reportlab==4.2.5
```
Expected: Successfully installed reportlab-4.2.5

- [ ] **Step 2: 建立 eightd_excel.py**

建立 `backend/services/eightd_excel.py`（完整內容如下）：

```python
"""AIAG 8D 報表 — Excel 格式（openpyxl）"""
from io import BytesIO
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side, numbers
from openpyxl.utils import get_column_letter


def _thin_border():
    thin = Side(style='thin')
    return Border(left=thin, right=thin, top=thin, bottom=thin)


def _hdr_font():
    return Font(name='微軟正黑體', size=11, bold=True, color='FFFFFF')


def _hdr_fill():
    return PatternFill(start_color='2B579A', end_color='2B579A', fill_type='solid')


def _lbl_fill():
    return PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')


def _cell(ws, row, col, value, bold=False, center=False, fill=None, border=True, wrap=False, font_size=10):
    c = ws.cell(row=row, column=col, value=value)
    c.font = Font(name='微軟正黑體', size=font_size, bold=bold)
    if center:
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=wrap)
    else:
        c.alignment = Alignment(vertical='center', wrap_text=wrap)
    if fill:
        c.fill = fill
    if border:
        c.border = _thin_border()
    return c


def generate_8d_excel(capa_data: dict) -> BytesIO:
    """從 CAPAService._to_dict() 回傳的 dict 產生 AIAG 8D Excel 報表"""
    wb = Workbook()
    ws = wb.active
    ws.title = 'AIAG 8D 報表'

    # 欄寬設定
    col_widths = [6, 20, 50, 20, 15]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ── 標題列 ────────────────────────────────────────────────
    ws.row_dimensions[1].height = 30
    ws.merge_cells('A1:E1')
    c = ws.cell(row=1, column=1, value='AIAG 8D 問題解決報告')
    c.font = Font(name='微軟正黑體', size=16, bold=True, color='FFFFFF')
    c.alignment = Alignment(horizontal='center', vertical='center')
    c.fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')

    # ── 基本資訊 ──────────────────────────────────────────────
    row = 2
    meta = [
        ('8D 單號',   capa_data.get('no', '')),
        ('來源類型',  'NCMR' if capa_data.get('source_type') == 'ncmr' else '客訴'),
        ('嚴重度',    capa_data.get('D0_severity') or ''),
        ('嚴格度',    capa_data.get('rigor', '')),
        ('狀態',      capa_data.get('status', '')),
        ('建立日期',  (capa_data.get('created_at') or '')[:10]),
        ('結案日期',  capa_data.get('D8_close_date') or ''),
    ]
    ws.merge_cells(f'A{row}:E{row}')
    _cell(ws, row, 1, '基本資訊', bold=True, center=True, fill=_hdr_fill(), font_size=11)
    c = ws.cell(row=row, column=1)
    c.font = _hdr_font()
    row += 1
    for label, val in meta:
        ws.merge_cells(f'A{row}:B{row}')
        _cell(ws, row, 1, label, bold=True, fill=_lbl_fill())
        ws.merge_cells(f'C{row}:E{row}')
        _cell(ws, row, 3, val)
        row += 1

    # 來源資訊
    src = capa_data.get('source_info') or {}
    if src:
        ws.merge_cells(f'A{row}:E{row}')
        _cell(ws, row, 1, '來源資訊', bold=True, center=True, fill=_hdr_fill(), font_size=11)
        ws.cell(row=row, column=1).font = _hdr_font()
        row += 1
        for k, v in src.items():
            ws.merge_cells(f'A{row}:B{row}')
            _cell(ws, row, 1, k, bold=True, fill=_lbl_fill())
            ws.merge_cells(f'C{row}:E{row}')
            _cell(ws, row, 3, v or '')
            row += 1

    def section_header(title: str):
        nonlocal row
        ws.row_dimensions[row].height = 22
        ws.merge_cells(f'A{row}:E{row}')
        c2 = ws.cell(row=row, column=1, value=title)
        c2.font = _hdr_font()
        c2.fill = _hdr_fill()
        c2.alignment = Alignment(horizontal='left', vertical='center')
        c2.border = _thin_border()
        row += 1

    def text_row(label: str, value: str, height: int = 15):
        nonlocal row
        ws.row_dimensions[row].height = height
        ws.merge_cells(f'A{row}:B{row}')
        _cell(ws, row, 1, label, bold=True, fill=_lbl_fill())
        ws.merge_cells(f'C{row}:E{row}')
        _cell(ws, row, 3, value or '', wrap=True)
        row += 1

    # ── D0 ───────────────────────────────────────────────────
    section_header('D0 緊急應對（Emergency Response）')
    text_row('症狀描述', capa_data.get('D0_symptom') or '', height=40)
    criteria = capa_data.get('D0_criteria') or []
    text_row('判斷準則', '、'.join(criteria) if criteria else '')
    text_row('客戶要求結案日', capa_data.get('D0_deadline') or '')

    # ── D1 ───────────────────────────────────────────────────
    section_header('D1 成立團隊（Team Formation）')
    text_row('Champion', capa_data.get('D1_champion_name') or '')
    text_row('Team Leader', capa_data.get('D1_leader_name') or '')

    # ── D2 ───────────────────────────────────────────────────
    section_header('D2 問題描述 5W2H（Problem Description）')
    for label, key in [
        ('What（是什麼）',   'D2_what'),
        ('Where（在哪裡）',  'D2_where'),
        ('When（何時）',     'D2_when'),
        ('Who（誰）',        'D2_who'),
        ('Why（為何出現）',  'D2_why'),
        ('How（如何發現）',  'D2_how'),
        ('How Many（數量）', 'D2_how_many'),
    ]:
        text_row(label, capa_data.get(key) or '', height=30)

    # ── D3 ───────────────────────────────────────────────────
    section_header('D3 暫時對策（Containment Action）')
    text_row('暫時對策內容', capa_data.get('D3_action') or '', height=50)
    text_row('生效日期', capa_data.get('D3_effective_date') or '')
    text_row('有效性驗證', capa_data.get('D3_verification') or '', height=30)

    # ── D4 ───────────────────────────────────────────────────
    section_header('D4 根本原因分析（Root Cause Analysis）')
    text_row('分析工具', capa_data.get('D4_tool') or '')

    tool = capa_data.get('D4_tool', '5why')
    if tool == '5why':
        five_why = capa_data.get('D4_five_why') or []
        for i, item in enumerate(five_why, 1):
            if isinstance(item, dict):
                text_row(f'Why {i}', f"{item.get('why','')} → {item.get('answer','')}", height=25)
    else:
        fishbone = capa_data.get('D4_fishbone') or {}
        for m_key, items in fishbone.items():
            if items:
                text_row(m_key, '、'.join(str(x) for x in items if x))

    text_row('根本原因（彙整）', capa_data.get('D4_root_cause') or '', height=50)

    # ── D5 ───────────────────────────────────────────────────
    section_header('D5 永久對策（Permanent Corrective Action）')
    text_row('永久對策內容', capa_data.get('D5_action') or '', height=50)
    text_row('預計實施日', capa_data.get('D5_planned_date') or '')
    text_row('驗證計畫', capa_data.get('D5_verify_plan') or '', height=30)

    # ── D6 ───────────────────────────────────────────────────
    section_header('D6 實施與驗證（Implementation & Verification）')
    text_row('實施日期', capa_data.get('D6_implement_date') or '')
    text_row('驗證結果', capa_data.get('D6_result') or '', height=50)
    text_row('驗證通過', '是' if capa_data.get('D6_verified') else '否')

    # ── D7 ───────────────────────────────────────────────────
    section_header('D7 橫向展開（Prevent Recurrence）')
    d7_actions = capa_data.get('D7_actions') or []
    checked = [a for a in d7_actions if isinstance(a, dict) and a.get('checked')]
    if checked:
        for a in checked:
            text_row(a.get('type', ''), a.get('description') or '')
    else:
        text_row('橫展項目', '（無）')

    # ── D8 ───────────────────────────────────────────────────
    section_header('D8 結案確認（Closure）')
    text_row('結案確認聲明', capa_data.get('D8_confirmation') or '', height=60)
    text_row('團隊表揚與心得', capa_data.get('D8_recognition') or '', height=40)
    text_row('結案日期', capa_data.get('D8_close_date') or '')

    # ── 頁尾 ──────────────────────────────────────────────────
    row += 1
    ws.merge_cells(f'A{row}:E{row}')
    c3 = ws.cell(row=row, column=1, value=f'產出日期：{datetime.now().strftime("%Y-%m-%d %H:%M")}')
    c3.font = Font(name='微軟正黑體', size=9, italic=True, color='808080')
    c3.alignment = Alignment(horizontal='right')

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
```

- [ ] **Step 3: 確認檔案可 import**

```bash
cd C:/QC_Database
./venv/Scripts/python -c "from backend.services.eightd_excel import generate_8d_excel; print('OK')"
```
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add backend/services/eightd_excel.py
git commit -m "feat: 新增 AIAG 8D Excel 報表服務（openpyxl）"
```

---

## Task 2: 建立 AIAG 8D PDF 報表服務

**Files:**
- Create: `backend/services/eightd_pdf.py`

前置條件：Task 1 的 reportlab 安裝已完成。

- [ ] **Step 1: 建立 eightd_pdf.py**

建立 `backend/services/eightd_pdf.py`（完整內容如下）：

```python
"""AIAG 8D 報表 — PDF 格式（reportlab）"""
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle,
    Spacer, HRFlowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# 嘗試註冊中文字型（若有），否則使用 Helvetica fallback
_FONT_REGISTERED = False
def _ensure_font():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    candidates = [
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        'C:/Windows/Fonts/msjh.ttc',
        'C:/Windows/Fonts/mingliu.ttc',
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont('CJK', path))
                _FONT_REGISTERED = True
                return
            except Exception:
                continue
    _FONT_REGISTERED = True  # 即使失敗也標記，避免重複嘗試


def _font_name() -> str:
    _ensure_font()
    return 'CJK' if _FONT_REGISTERED and 'CJK' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'


# 顏色
CLR_DARK_BLUE = colors.HexColor('#1F4E79')
CLR_MID_BLUE = colors.HexColor('#2B579A')
CLR_LIGHT_BLUE = colors.HexColor('#D9E1F2')
CLR_WHITE = colors.white
CLR_GRAY = colors.HexColor('#808080')


def _para(text: str, style=None) -> Paragraph:
    """建立 Paragraph，若 style 為 None 則使用基本 Normal"""
    fn = _font_name()
    if style is None:
        style = ParagraphStyle('base', fontName=fn, fontSize=9, leading=13)
    return Paragraph(str(text or ''), style)


def _section_table(title: str, rows: list[tuple[str, str]]) -> Table:
    """建立一個 section 的雙欄表格（標題列 + 欄位列）"""
    fn = _font_name()
    title_style = ParagraphStyle('title', fontName=fn, fontSize=10, textColor=CLR_WHITE, leading=14)
    label_style = ParagraphStyle('label', fontName=fn, fontSize=9, textColor=CLR_DARK_BLUE, leading=12)
    val_style   = ParagraphStyle('val',   fontName=fn, fontSize=9, leading=13)

    data = [[Paragraph(title, title_style), '']]
    for label, val in rows:
        data.append([Paragraph(label, label_style), Paragraph(str(val or ''), val_style)])

    col_widths = [45 * mm, 125 * mm]
    t = Table(data, colWidths=col_widths)
    n = len(data)
    style_cmds = [
        # 標題
        ('BACKGROUND',  (0, 0), (1, 0), CLR_MID_BLUE),
        ('SPAN',        (0, 0), (1, 0)),
        ('TEXTCOLOR',   (0, 0), (1, 0), CLR_WHITE),
        ('FONTNAME',    (0, 0), (1, 0), fn),
        ('FONTSIZE',    (0, 0), (1, 0), 11),
        ('TOPPADDING',  (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        # 資料列交替背景
        ('BACKGROUND',  (0, 1), (0, n - 1), CLR_LIGHT_BLUE),
        # 格線
        ('GRID',        (0, 0), (-1, -1), 0.5, colors.HexColor('#BBBBBB')),
        ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
    ]
    t.setStyle(TableStyle(style_cmds))
    return t


def generate_8d_pdf(capa_data: dict) -> BytesIO:
    """從 CAPAService._to_dict() 回傳的 dict 產生 AIAG 8D PDF 報表"""
    buf = BytesIO()
    fn = _font_name()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"AIAG 8D 報告 {capa_data.get('no', '')}",
    )

    story = []
    h1_style = ParagraphStyle('h1', fontName=fn, fontSize=16, textColor=CLR_WHITE, leading=20, spaceAfter=2)
    sub_style = ParagraphStyle('sub', fontName=fn, fontSize=9, textColor=CLR_GRAY, leading=12)

    # ── 封面標題 ──────────────────────────────────────────────
    title_data = [[Paragraph('AIAG 8D 問題解決報告', h1_style)]]
    title_table = Table(title_data, colWidths=[170 * mm])
    title_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CLR_DARK_BLUE),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(title_table)
    story.append(Spacer(1, 4 * mm))

    # ── 基本資訊 ──────────────────────────────────────────────
    src = capa_data.get('source_info') or {}
    meta_rows = [
        ('8D 單號',     capa_data.get('no', '')),
        ('來源',        'NCMR' if capa_data.get('source_type') == 'ncmr' else '客訴'),
        ('嚴重度',      capa_data.get('D0_severity') or ''),
        ('嚴格度',      capa_data.get('rigor', '')),
        ('狀態',        capa_data.get('status', '')),
        ('建立日期',    (capa_data.get('created_at') or '')[:10]),
    ] + [(k, v or '') for k, v in src.items()]
    story.append(_section_table('基本資訊 / Header', meta_rows))
    story.append(Spacer(1, 3 * mm))

    # ── D0 ───────────────────────────────────────────────────
    criteria = capa_data.get('D0_criteria') or []
    story.append(_section_table('D0 緊急應對 Emergency Response', [
        ('症狀描述',       capa_data.get('D0_symptom') or ''),
        ('判斷準則',       '、'.join(criteria) if criteria else ''),
        ('客戶要求結案日', capa_data.get('D0_deadline') or ''),
    ]))
    story.append(Spacer(1, 3 * mm))

    # ── D1 ───────────────────────────────────────────────────
    story.append(_section_table('D1 成立團隊 Team Formation', [
        ('Champion',     capa_data.get('D1_champion_name') or ''),
        ('Team Leader',  capa_data.get('D1_leader_name') or ''),
    ]))
    story.append(Spacer(1, 3 * mm))

    # ── D2 ───────────────────────────────────────────────────
    story.append(_section_table('D2 問題描述 5W2H Problem Description', [
        ('What（是什麼）',   capa_data.get('D2_what') or ''),
        ('Where（在哪裡）',  capa_data.get('D2_where') or ''),
        ('When（何時）',     capa_data.get('D2_when') or ''),
        ('Who（誰）',        capa_data.get('D2_who') or ''),
        ('Why（為何出現）',  capa_data.get('D2_why') or ''),
        ('How（如何發現）',  capa_data.get('D2_how') or ''),
        ('How Many（數量）', capa_data.get('D2_how_many') or ''),
    ]))
    story.append(Spacer(1, 3 * mm))

    # ── D3 ───────────────────────────────────────────────────
    story.append(_section_table('D3 暫時對策 Containment Action', [
        ('暫時對策內容', capa_data.get('D3_action') or ''),
        ('生效日期',     capa_data.get('D3_effective_date') or ''),
        ('有效性驗證',   capa_data.get('D3_verification') or ''),
    ]))
    story.append(Spacer(1, 3 * mm))

    # ── D4 ───────────────────────────────────────────────────
    d4_rows = [('分析工具', capa_data.get('D4_tool') or '')]
    tool = capa_data.get('D4_tool', '5why')
    if tool == '5why':
        for i, item in enumerate((capa_data.get('D4_five_why') or []), 1):
            if isinstance(item, dict):
                d4_rows.append((f'Why {i}', f"{item.get('why','')} → {item.get('answer','')}"))
    else:
        fishbone = capa_data.get('D4_fishbone') or {}
        for m_key, items in fishbone.items():
            if items:
                d4_rows.append((m_key, '、'.join(str(x) for x in items if x)))
    d4_rows.append(('根本原因（彙整）', capa_data.get('D4_root_cause') or ''))
    story.append(_section_table('D4 根本原因分析 Root Cause Analysis', d4_rows))
    story.append(Spacer(1, 3 * mm))

    # ── D5 ───────────────────────────────────────────────────
    story.append(_section_table('D5 永久對策 Permanent Corrective Action', [
        ('永久對策內容', capa_data.get('D5_action') or ''),
        ('預計實施日',   capa_data.get('D5_planned_date') or ''),
        ('驗證計畫',     capa_data.get('D5_verify_plan') or ''),
    ]))
    story.append(Spacer(1, 3 * mm))

    # ── D6 ───────────────────────────────────────────────────
    story.append(_section_table('D6 實施與驗證 Implementation & Verification', [
        ('實施日期',   capa_data.get('D6_implement_date') or ''),
        ('驗證結果',   capa_data.get('D6_result') or ''),
        ('驗證通過',   '是' if capa_data.get('D6_verified') else '否'),
    ]))
    story.append(Spacer(1, 3 * mm))

    # ── D7 ───────────────────────────────────────────────────
    d7_actions = capa_data.get('D7_actions') or []
    checked = [a for a in d7_actions if isinstance(a, dict) and a.get('checked')]
    d7_rows = [(a.get('type', ''), a.get('description') or '') for a in checked] or [('（無橫展項目）', '')]
    story.append(_section_table('D7 橫向展開 Prevent Recurrence', d7_rows))
    story.append(Spacer(1, 3 * mm))

    # ── D8 ───────────────────────────────────────────────────
    story.append(_section_table('D8 結案確認 Closure', [
        ('結案確認聲明',   capa_data.get('D8_confirmation') or ''),
        ('團隊表揚與心得', capa_data.get('D8_recognition') or ''),
        ('結案日期',       capa_data.get('D8_close_date') or ''),
    ]))
    story.append(Spacer(1, 5 * mm))

    # ── 頁尾 ──────────────────────────────────────────────────
    story.append(Paragraph(
        f'產出日期：{datetime.now().strftime("%Y-%m-%d %H:%M")}　｜　QMS 系統自動產出',
        ParagraphStyle('footer', fontName=fn, fontSize=8, textColor=CLR_GRAY, alignment=2),
    ))

    doc.build(story)
    buf.seek(0)
    return buf
```

- [ ] **Step 2: 確認可 import**

```bash
cd C:/QC_Database
./venv/Scripts/python -c "from backend.services.eightd_pdf import generate_8d_pdf; print('OK')"
```
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add backend/services/eightd_pdf.py
git commit -m "feat: 新增 AIAG 8D PDF 報表服務（reportlab）"
```

---

## Task 3: 完成後端匯出路由

**Files:**
- Modify: `backend/routes/capa.py:165-177`

- [ ] **Step 1: 更新 download_pdf 和 download_excel 路由**

將 `backend/routes/capa.py` 中的 `download_pdf` 和 `download_excel` 函式改為：

```python
# ── 報表下載 ────────────────────────────────────────────────────
@capa_bp.route('/api/capas/<int:capa_id>/report/pdf', methods=['GET'])
@auth_required
def download_pdf(current_user, capa_id: int):
    """GET /api/capas/<id>/report/pdf — 下載 AIAG 8D 報表 PDF"""
    detail = CAPAService.get_detail(capa_id)
    if not detail:
        return jsonify({'error': 'CAPA 不存在'}), 404
    try:
        from ..services.eightd_pdf import generate_8d_pdf
        from flask import send_file
        buf = generate_8d_pdf(detail)
        filename = f"8D_{detail.get('no', capa_id)}.pdf"
        return send_file(
            buf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@capa_bp.route('/api/capas/<int:capa_id>/report/excel', methods=['GET'])
@auth_required
def download_excel(current_user, capa_id: int):
    """GET /api/capas/<id>/report/excel — 下載 AIAG 8D 報表 Excel"""
    detail = CAPAService.get_detail(capa_id)
    if not detail:
        return jsonify({'error': 'CAPA 不存在'}), 404
    try:
        from ..services.eightd_excel import generate_8d_excel
        from flask import send_file
        buf = generate_8d_excel(detail)
        filename = f"8D_{detail.get('no', capa_id)}.xlsx"
        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

- [ ] **Step 2: Commit**

```bash
git add backend/routes/capa.py
git commit -m "feat: 完成 AIAG 8D 報表 PDF/Excel 下載路由"
```

---

## Task 4: 前端 CAPA 匯出按鈕

**Files:**
- Modify: `src_frontend/src/hooks/useCapa.ts`
- Modify: `src_frontend/src/components/capa/CAPAModal.tsx`

- [ ] **Step 1: 在 useCapa.ts 末尾加入 export 工具函式**

在 `src_frontend/src/hooks/useCapa.ts` 末尾加入：

```typescript
// ── 8D 報表下載 ────────────────────────────────────────────────
export const download8DReport = async (capaId: number, format: 'pdf' | 'excel') => {
    const ext  = format === 'pdf' ? 'pdf' : 'xlsx';
    const mime = format === 'pdf'
        ? 'application/pdf'
        : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

    const res = await api.get(`/capas/${capaId}/report/${format}`, {
        responseType: 'blob',
    });

    const url = URL.createObjectURL(new Blob([res.data], { type: mime }));
    const a   = document.createElement('a');
    a.href    = url;
    a.download = `8D_${capaId}.${ext}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
};
```

- [ ] **Step 2: 在 CAPAModal.tsx 的 Modal.Footer 加入匯出按鈕**

找到 `CAPAModal.tsx` 中的 `<Modal.Footer>` 區塊（約第 584 行），在 `<Button variant="secondary" ...>關閉</Button>` 之前加入：

```typescript
{capa && !isLoading && (
    <div className="d-flex gap-2">
        <Button
            variant="outline-success"
            size="sm"
            onClick={async () => {
                try {
                    await download8DReport(capa.id, 'excel');
                } catch {
                    toast.error('Excel 匯出失敗');
                }
            }}
        >
            <i className="bi bi-file-earmark-excel me-1" />
            匯出 Excel
        </Button>
        <Button
            variant="outline-danger"
            size="sm"
            onClick={async () => {
                try {
                    await download8DReport(capa.id, 'pdf');
                } catch {
                    toast.error('PDF 匯出失敗');
                }
            }}
        >
            <i className="bi bi-file-earmark-pdf me-1" />
            匯出 PDF
        </Button>
    </div>
)}
```

同時在 import 列加入 `toast` 和 `download8DReport`：
```typescript
import toast from 'react-hot-toast';
import { ..., download8DReport } from '../../hooks/useCapa';
```

- [ ] **Step 3: TypeScript 編譯確認**

```bash
cd C:/QC_Database/src_frontend
npm run build 2>&1 | tail -20
```
Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add src_frontend/src/hooks/useCapa.ts src_frontend/src/components/capa/CAPAModal.tsx
git commit -m "feat: CAPAModal 加入 8D 報表匯出按鈕（PDF + Excel）"
```

---

## Task 5: 客訴統計圖表頁

**Files:**
- Create: `src_frontend/src/pages/complaint/ComplaintStatsPage.tsx`
- Modify: `src_frontend/src/App.tsx`

- [ ] **Step 1: 建立 ComplaintStatsPage.tsx**

建立 `src_frontend/src/pages/complaint/ComplaintStatsPage.tsx`（完整內容如下）：

```typescript
import { useState } from 'react';
import { Container, Card, Row, Col, Form, Button, Spinner } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import {
    Chart as ChartJS,
    CategoryScale, LinearScale, BarElement, ArcElement,
    PointElement, LineElement, Title, Tooltip, Legend,
} from 'chart.js';
import { Bar, Line, Doughnut } from 'react-chartjs-2';
import {
    useComplaintStatsByCustomer,
    useComplaintStatsByProduct,
    useComplaintStatsByMonth,
    useComplaintStatsWarranty,
} from '../../hooks/useComplaint';

ChartJS.register(
    CategoryScale, LinearScale, BarElement, ArcElement,
    PointElement, LineElement, Title, Tooltip, Legend,
);

const CHART_COLORS = ['#2B579A','#4472C4','#5B9BD5','#9DC3E6','#BDD7EE','#DDEBF7'];

const ComplaintStatsPage = () => {
    const navigate = useNavigate();
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');
    const [appliedFrom, setAppliedFrom] = useState<string | undefined>(undefined);
    const [appliedTo, setAppliedTo] = useState<string | undefined>(undefined);

    const applyFilter = () => {
        setAppliedFrom(dateFrom || undefined);
        setAppliedTo(dateTo || undefined);
    };
    const resetFilter = () => {
        setDateFrom(''); setDateTo('');
        setAppliedFrom(undefined); setAppliedTo(undefined);
    };

    const fp = { date_from: appliedFrom, date_to: appliedTo };

    const { data: byCustomer, isLoading: l1 } = useComplaintStatsByCustomer(fp);
    const { data: byProduct,  isLoading: l2 } = useComplaintStatsByProduct(fp);
    const { data: byMonth,    isLoading: l3 } = useComplaintStatsByMonth(fp);
    const { data: warranty,   isLoading: l4 } = useComplaintStatsWarranty(fp);

    const anyLoading = l1 || l2 || l3 || l4;

    return (
        <Container fluid className="py-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h4 className="mb-0">
                    <i className="bi bi-bar-chart-fill me-2 text-primary" />
                    客訴統計分析
                </h4>
                <Button variant="outline-secondary" size="sm" onClick={() => navigate('/complaints')}>
                    <i className="bi bi-arrow-left me-1" />
                    返回客訴列表
                </Button>
            </div>

            {/* 日期篩選 */}
            <Card className="mb-4 shadow-sm">
                <Card.Body className="py-2">
                    <Row className="g-2 align-items-end">
                        <Col xs={6} md={3}>
                            <Form.Label className="small mb-1">日期（起）</Form.Label>
                            <Form.Control type="date" size="sm" value={dateFrom}
                                onChange={e => setDateFrom(e.target.value)} />
                        </Col>
                        <Col xs={6} md={3}>
                            <Form.Label className="small mb-1">日期（迄）</Form.Label>
                            <Form.Control type="date" size="sm" value={dateTo}
                                onChange={e => setDateTo(e.target.value)} />
                        </Col>
                        <Col xs={6} md={2}>
                            <Button variant="primary" size="sm" className="w-100" onClick={applyFilter}>套用</Button>
                        </Col>
                        <Col xs={6} md={2}>
                            <Button variant="outline-secondary" size="sm" className="w-100" onClick={resetFilter}>清除</Button>
                        </Col>
                    </Row>
                </Card.Body>
            </Card>

            {anyLoading ? (
                <div className="text-center py-5">
                    <Spinner animation="border" />
                    <div className="mt-2 text-muted">統計資料載入中…</div>
                </div>
            ) : (
                <Row className="g-4">
                    {/* 月趨勢折線圖 */}
                    <Col md={12}>
                        <Card className="shadow-sm">
                            <Card.Header className="fw-semibold">每月客訴件數趨勢</Card.Header>
                            <Card.Body>
                                {byMonth && byMonth.length > 0 ? (
                                    <Line
                                        data={{
                                            labels: byMonth.map(d => d.year_month),
                                            datasets: [{
                                                label: '客訴件數',
                                                data: byMonth.map(d => d.total),
                                                borderColor: CHART_COLORS[0],
                                                backgroundColor: CHART_COLORS[0] + '33',
                                                tension: 0.3,
                                                fill: true,
                                            }],
                                        }}
                                        options={{
                                            responsive: true,
                                            plugins: { legend: { position: 'top' } },
                                            scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
                                        }}
                                        height={80}
                                    />
                                ) : <p className="text-muted text-center">無資料</p>}
                            </Card.Body>
                        </Card>
                    </Col>

                    {/* 客戶別橫條圖 */}
                    <Col md={6}>
                        <Card className="shadow-sm">
                            <Card.Header className="fw-semibold">客戶別客訴件數（Top 10）</Card.Header>
                            <Card.Body>
                                {byCustomer && byCustomer.length > 0 ? (
                                    <Bar
                                        data={{
                                            labels: byCustomer.slice(0, 10).map(d => d.customer),
                                            datasets: [
                                                {
                                                    label: '客訴件數',
                                                    data: byCustomer.slice(0, 10).map(d => d.total),
                                                    backgroundColor: CHART_COLORS[0],
                                                },
                                                {
                                                    label: '重複客訴',
                                                    data: byCustomer.slice(0, 10).map(d => d.repeat_count),
                                                    backgroundColor: CHART_COLORS[3],
                                                },
                                            ],
                                        }}
                                        options={{
                                            responsive: true,
                                            plugins: { legend: { position: 'top' } },
                                            scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
                                        }}
                                    />
                                ) : <p className="text-muted text-center">無資料</p>}
                            </Card.Body>
                        </Card>
                    </Col>

                    {/* 料號別橫條圖 */}
                    <Col md={6}>
                        <Card className="shadow-sm">
                            <Card.Header className="fw-semibold">料號別客訴件數（Top 10）</Card.Header>
                            <Card.Body>
                                {byProduct && byProduct.length > 0 ? (
                                    <Bar
                                        data={{
                                            labels: byProduct.slice(0, 10).map(d => d.product_no),
                                            datasets: [
                                                {
                                                    label: '客訴件數',
                                                    data: byProduct.slice(0, 10).map(d => d.total),
                                                    backgroundColor: CHART_COLORS[1],
                                                },
                                                {
                                                    label: '重複客訴',
                                                    data: byProduct.slice(0, 10).map(d => d.repeat_count),
                                                    backgroundColor: CHART_COLORS[4],
                                                },
                                            ],
                                        }}
                                        options={{
                                            responsive: true,
                                            plugins: { legend: { position: 'top' } },
                                            scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
                                        }}
                                    />
                                ) : <p className="text-muted text-center">無資料</p>}
                            </Card.Body>
                        </Card>
                    </Col>

                    {/* 保固統計 */}
                    {warranty && (
                        <Col md={12}>
                            <Card className="shadow-sm">
                                <Card.Header className="fw-semibold">保固 / 現場故障統計</Card.Header>
                                <Card.Body>
                                    <Row className="g-3">
                                        <Col md={3}>
                                            <div className="text-center border rounded p-3">
                                                <div className="fs-3 fw-bold text-primary">{warranty.total}</div>
                                                <div className="small text-muted">總件數</div>
                                            </div>
                                        </Col>
                                        <Col md={3}>
                                            <div className="text-center border rounded p-3">
                                                <div className="fs-3 fw-bold text-warning">{warranty.warranty_count}</div>
                                                <div className="small text-muted">保固申請</div>
                                            </div>
                                        </Col>
                                        <Col md={3}>
                                            <div className="text-center border rounded p-3">
                                                <div className="fs-3 fw-bold text-danger">{warranty.field_failure_count}</div>
                                                <div className="small text-muted">現場故障</div>
                                            </div>
                                        </Col>
                                        <Col md={3}>
                                            <div className="text-center border rounded p-3">
                                                <div className="fs-3 fw-bold text-info">
                                                    {warranty.avg_failure_hours != null
                                                        ? warranty.avg_failure_hours.toFixed(0)
                                                        : '—'}
                                                </div>
                                                <div className="small text-muted">平均故障時數</div>
                                            </div>
                                        </Col>
                                    </Row>

                                    {warranty.by_product && warranty.by_product.length > 0 && (
                                        <div className="mt-4">
                                            <h6 className="fw-semibold mb-3">料號別保固 / 故障件數</h6>
                                            <Bar
                                                data={{
                                                    labels: warranty.by_product.slice(0, 10).map(d => d.product_no),
                                                    datasets: [{
                                                        label: '件數',
                                                        data: warranty.by_product.slice(0, 10).map(d => d.total),
                                                        backgroundColor: CHART_COLORS[2],
                                                    }],
                                                }}
                                                options={{
                                                    responsive: true,
                                                    plugins: { legend: { display: false } },
                                                    scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
                                                }}
                                                height={60}
                                            />
                                        </div>
                                    )}
                                </Card.Body>
                            </Card>
                        </Col>
                    )}
                </Row>
            )}
        </Container>
    );
};

export default ComplaintStatsPage;
```

- [ ] **Step 2: 在 App.tsx 加入路由**

在 `src_frontend/src/App.tsx` 找到 `complaints` 路由後面加入：
```typescript
import ComplaintStatsPage from './pages/complaint/ComplaintStatsPage';
// ...
<Route path="/complaints/stats" element={<ComplaintStatsPage />} />
```
（放在 `/complaints` route 後面）

- [ ] **Step 3: 在 ComplaintPage 加入「統計分析」按鈕**

在 `ComplaintPage.tsx` 的標題列（`d-flex justify-content-between`）區塊中，加入連結按鈕：
```typescript
import { useNavigate } from 'react-router-dom';
// 在按鈕列加入：
<Button variant="outline-primary" size="sm" onClick={() => navigate('/complaints/stats')}>
    <i className="bi bi-bar-chart-fill me-1" />
    統計分析
</Button>
```

- [ ] **Step 4: TypeScript 編譯確認**

```bash
cd C:/QC_Database/src_frontend
npm run build 2>&1 | tail -20
```
Expected: 0 errors

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/pages/complaint/ComplaintStatsPage.tsx src_frontend/src/App.tsx src_frontend/src/pages/complaint/ComplaintPage.tsx
git commit -m "feat: 新增客訴統計圖表頁（月趨勢/客戶別/料號別/保固）"
```

---

## Task 6: CARA 前端調整（對接新版 API）

**Files:**
- Create: `src_frontend/src/hooks/useCARA.ts`
- Modify: `src_frontend/src/components/cara/CARAModal.tsx`

### 背景
後端已有完整新版 CARA API（`/api/caras/<id>`, `/api/caras/<id>/step`, `/api/caras/<id>/close`），
但 `CARAModal.tsx` 仍使用舊版 `/cara/detail/<id>` 和 `/cara/update` 端點，需要重寫。

- [ ] **Step 1: 建立 useCARA.ts**

建立 `src_frontend/src/hooks/useCARA.ts`（完整內容如下）：

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import toast from 'react-hot-toast';
import type { CARADetail, PaginatedResponse } from '../types';

export interface CARAListParams {
    status?: string;
    vendor?: string;
    date_from?: string;
    date_to?: string;
    page?: number;
    per_page?: number;
}

// ── CARA 明細 ─────────────────────────────────────────────────
export const useCARADetail = (id: number | null) =>
    useQuery({
        queryKey: ['caraDetail', id],
        queryFn: async () => {
            const res = await api.get<CARADetail>(`/caras/${id}`);
            return res.data;
        },
        enabled: !!id,
    });

// ── 步驟更新 ─────────────────────────────────────────────────
export const useUpdateCARAStep = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, data }: { id: number; data: Record<string, unknown> }) => {
            const res = await api.patch<CARADetail>(`/caras/${id}/step`, data);
            return res.data;
        },
        onSuccess: (_data, vars) => {
            toast.success('儲存成功');
            qc.invalidateQueries({ queryKey: ['caraDetail', vars.id] });
            qc.invalidateQueries({ queryKey: ['caraList'] });
        },
        onError: (err: Error) => {
            toast.error(`儲存失敗：${err.message}`);
        },
    });
};

// ── D8 結案 ───────────────────────────────────────────────────
export const useCloseCARA = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, D8_confirmation }: { id: number; D8_confirmation: string }) => {
            const res = await api.post<CARADetail>(`/caras/${id}/close`, { D8_confirmation });
            return res.data;
        },
        onSuccess: (_data, vars) => {
            toast.success('CARA 已結案');
            qc.invalidateQueries({ queryKey: ['caraDetail', vars.id] });
            qc.invalidateQueries({ queryKey: ['caraList'] });
        },
        onError: (err: Error) => {
            toast.error(`結案失敗：${err.message}`);
        },
    });
};

// ── 刪除 CARA ─────────────────────────────────────────────────
export const useDeleteCARA = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (id: number) => {
            await api.delete(`/caras/${id}`);
        },
        onSuccess: () => {
            toast.success('CARA 已刪除');
            qc.invalidateQueries({ queryKey: ['caraList'] });
        },
    });
};

export const CARA_STEP_LABELS: Record<number, string> = {
    2: 'D2 問題描述',
    3: 'D3 暫時對策',
    4: 'D4 根本原因',
    6: 'D6 實施驗證',
    8: 'D8 結案確認',
};
```

- [ ] **Step 2: 重寫 CARAModal.tsx**

用以下內容完整替換 `src_frontend/src/components/cara/CARAModal.tsx`：

```typescript
import { useState, useEffect } from 'react';
import {
    Modal, Button, Form, Nav, Tab, Row, Col,
    Alert, Badge, ProgressBar, Spinner, Table,
} from 'react-bootstrap';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import {
    useCARADetail,
    useUpdateCARAStep,
    useCloseCARA,
    CARA_STEP_LABELS,
} from '../../hooks/useCARA';

// CARA 步驟列表（簡化5D）
const CARA_STEPS = [2, 3, 4, 6, 8];

interface CARAModalProps {
    show: boolean;
    caraId: number | null;
    onHide: () => void;
}

// Hook：取得檢驗員清單
const useInspectors = () =>
    useQuery({
        queryKey: ['inspectors'],
        queryFn: async () => {
            const res = await api.get('/auth/inspectors');
            return res.data as { id: number; name: string }[];
        },
        staleTime: 10 * 60 * 1000,
    });

// 儲存按鈕列
const SaveBar = ({ onSave, saving, readonly }: { onSave: () => void; saving: boolean; readonly?: boolean }) => {
    if (readonly) return <Alert variant="secondary" className="mt-3 py-2 small">此 CARA 已結案，無法編輯。</Alert>;
    return (
        <div className="d-flex justify-content-end mt-3">
            <Button variant="primary" size="sm" onClick={onSave} disabled={saving}>
                {saving ? <Spinner size="sm" animation="border" className="me-1" /> : <i className="bi bi-save me-1" />}
                儲存此步驟
            </Button>
        </div>
    );
};

// 5Why 編輯器（共用邏輯，與 CAPAModal 一致）
interface FiveWhyRow { why: string; answer: string }
const FiveWhyEditor = ({ value, onChange, readonly }: {
    value: FiveWhyRow[]; onChange: (rows: FiveWhyRow[]) => void; readonly?: boolean;
}) => {
    const rows = value?.length >= 3 ? value : Array.from({ length: 3 }, (_, i) => value?.[i] ?? { why: '', answer: '' });
    const update = (idx: number, field: keyof FiveWhyRow, val: string) =>
        onChange(rows.map((r, i) => i === idx ? { ...r, [field]: val } : r));
    return (
        <div>
            <Table size="sm" bordered className="mb-2">
                <thead className="table-light">
                    <tr><th style={{ width: '60px' }}>#</th><th>為什麼</th><th>原因</th></tr>
                </thead>
                <tbody>
                    {rows.map((r, i) => (
                        <tr key={i}>
                            <td className="text-center fw-bold text-primary">Why {i + 1}</td>
                            <td><Form.Control size="sm" value={r.why} onChange={e => update(i, 'why', e.target.value)} disabled={readonly} placeholder="請輸入為什麼…" /></td>
                            <td><Form.Control size="sm" value={r.answer} onChange={e => update(i, 'answer', e.target.value)} disabled={readonly} placeholder="請輸入原因…" /></td>
                        </tr>
                    ))}
                </tbody>
            </Table>
            {!readonly && (
                <div className="d-flex gap-2">
                    <Button size="sm" variant="outline-secondary" onClick={() => onChange(rows.slice(0, -1))} disabled={rows.length <= 3}>
                        <i className="bi bi-dash" /> 移除一層
                    </Button>
                    <Button size="sm" variant="outline-primary" onClick={() => onChange([...rows, { why: '', answer: '' }])} disabled={rows.length >= 7}>
                        <i className="bi bi-plus" /> 增加一層
                    </Button>
                </div>
            )}
        </div>
    );
};

// ── 主元件 ────────────────────────────────────────────────────
const CARAModal = ({ show, caraId, onHide }: CARAModalProps) => {
    const { data: cara, isLoading } = useCARADetail(caraId);
    const { data: inspectors = [] }  = useInspectors();
    const updateStep = useUpdateCARAStep();
    const closeMut   = useCloseCARA();

    const [activeTab, setActiveTab] = useState('d2');

    // D1
    const [d1Leader, setD1Leader] = useState<number | ''>('');
    // D2
    const [d2What, setD2What]     = useState('');
    const [d2Where, setD2Where]   = useState('');
    const [d2When, setD2When]     = useState('');
    const [d2Who, setD2Who]       = useState('');
    const [d2Why, setD2Why]       = useState('');
    const [d2How, setD2How]       = useState('');
    const [d2HowMany, setD2HowMany] = useState('');
    // D3
    const [d3Action, setD3Action]     = useState('');
    const [d3EffDate, setD3EffDate]   = useState('');
    const [d3Verif, setD3Verif]       = useState('');
    // D4
    const [d4Tool, setD4Tool]         = useState('5why');
    const [d4FiveWhy, setD4FiveWhy]   = useState<FiveWhyRow[]>([]);
    const [d4Fishbone, setD4Fishbone] = useState<Record<string, string[]>>({});
    const [d4RootCause, setD4RootCause] = useState('');
    // D6
    const [d6ImplDate, setD6ImplDate] = useState('');
    const [d6Result, setD6Result]     = useState('');
    const [d6Verified, setD6Verified] = useState(false);
    // D8
    const [d8Confirm, setD8Confirm]   = useState('');

    const isClosed = cara?.status === '已結案';

    useEffect(() => {
        if (!cara) return;
        setD1Leader(cara.D1_leader_id ?? '');
        setD2What(cara.D2_what ?? '');
        setD2Where(cara.D2_where ?? '');
        setD2When(cara.D2_when ?? '');
        setD2Who(cara.D2_who ?? '');
        setD2Why(cara.D2_why ?? '');
        setD2How(cara.D2_how ?? '');
        setD2HowMany(cara.D2_how_many ?? '');
        setD3Action(cara.D3_action ?? '');
        setD3EffDate(cara.D3_effective_date ?? '');
        setD3Verif(cara.D3_verification ?? '');
        setD4Tool(cara.D4_tool ?? '5why');
        setD4FiveWhy((cara.D4_five_why ?? []) as FiveWhyRow[]);
        setD4Fishbone((cara.D4_fishbone ?? {}) as Record<string, string[]>);
        setD4RootCause(cara.D4_root_cause ?? '');
        setD6ImplDate(cara.D6_implement_date ?? '');
        setD6Result(cara.D6_result ?? '');
        setD6Verified(cara.D6_verified ?? false);
        setD8Confirm(cara.D8_confirmation ?? '');
    }, [cara]);

    const saveStep = (stepKey: string, payload: Record<string, unknown>) => {
        if (!caraId) return;
        updateStep.mutate({ id: caraId, data: { step: stepKey, ...payload } });
    };

    const stepDone = (n: number) =>
        cara?.progress?.step_status?.[`D${n}`] === true;

    if (!show) return null;

    return (
        <Modal show={show} onHide={onHide} size="xl" backdrop="static" scrollable>
            <Modal.Header closeButton>
                <Modal.Title>
                    <i className="bi bi-clipboard-check me-2 text-warning" />
                    CARA {cara?.no ?? '—'}
                    {isClosed && <Badge bg="success" className="ms-2 fs-6">已結案</Badge>}
                </Modal.Title>
            </Modal.Header>

            <Modal.Body>
                {isLoading ? (
                    <div className="text-center py-5">
                        <Spinner animation="border" />
                        <div className="mt-2 text-muted small">載入中…</div>
                    </div>
                ) : !cara ? (
                    <Alert variant="warning">找不到 CARA 資料</Alert>
                ) : (
                    <>
                        {/* 整體進度條 */}
                        <div className="mb-3">
                            <div className="d-flex justify-content-between align-items-center mb-1">
                                <span className="small fw-semibold">整體進度</span>
                                <span className="small text-muted">
                                    {cara.progress.completed_steps}/{cara.progress.total_steps} 步驟完成
                                </span>
                            </div>
                            <ProgressBar
                                now={cara.progress.percent}
                                variant={cara.progress.percent >= 100 ? 'success' : cara.progress.percent >= 50 ? 'primary' : 'warning'}
                                label={`${cara.progress.percent}%`}
                                style={{ height: '12px' }}
                            />
                        </div>

                        {/* 來源 NCMR 資訊 */}
                        {cara.ncmr_info && Object.keys(cara.ncmr_info).length > 0 && (
                            <Alert variant="light" className="border mb-3 py-2">
                                <Row className="small g-2 align-items-center">
                                    <Col xs="auto">
                                        <Badge bg="warning" text="dark">NCMR</Badge>
                                        <span className="ms-1 fw-semibold">#{cara.ncmr_id}</span>
                                    </Col>
                                    {Object.entries(cara.ncmr_info).slice(0, 4).map(([k, v]) => (
                                        <Col xs="auto" key={k}>
                                            <span className="text-muted">{k}：</span>
                                            <span>{v ?? '—'}</span>
                                        </Col>
                                    ))}
                                </Row>
                            </Alert>
                        )}

                        {/* 步驟 Tab */}
                        <Tab.Container activeKey={activeTab} onSelect={k => k && setActiveTab(k)}>
                            <Nav variant="pills" className="mb-3 flex-wrap gap-1">
                                {CARA_STEPS.map(n => (
                                    <Nav.Item key={n}>
                                        <Nav.Link eventKey={`d${n}`} className="py-1 px-2 small">
                                            {stepDone(n)
                                                ? <i className="bi bi-check-circle-fill text-success me-1" />
                                                : <i className="bi bi-circle me-1 text-muted" />
                                            }
                                            {CARA_STEP_LABELS[n]}
                                        </Nav.Link>
                                    </Nav.Item>
                                ))}
                            </Nav>
                            <Tab.Content>
                                {/* D2 */}
                                <Tab.Pane eventKey="d2">
                                    <div>
                                        <Form.Label className="fw-semibold mb-2">負責人</Form.Label>
                                        <Form.Select className="mb-3" value={d1Leader} onChange={e => setD1Leader(e.target.value ? Number(e.target.value) : '')} disabled={isClosed}>
                                            <option value="">請選擇</option>
                                            {inspectors.map(i => <option key={i.id} value={i.id}>{i.name}</option>)}
                                        </Form.Select>
                                        <hr className="my-2" />
                                        <Row className="g-3">
                                            {[
                                                { label: 'What（是什麼）', val: d2What, set: setD2What },
                                                { label: 'Where（在哪裡）', val: d2Where, set: setD2Where },
                                                { label: 'When（何時）', val: d2When, set: setD2When },
                                                { label: 'Who（誰）', val: d2Who, set: setD2Who },
                                                { label: 'Why（為何出現）', val: d2Why, set: setD2Why },
                                                { label: 'How（如何發現）', val: d2How, set: setD2How },
                                                { label: 'How Many（數量）', val: d2HowMany, set: setD2HowMany },
                                            ].map(f => (
                                                <Col md={6} key={f.label}>
                                                    <Form.Group>
                                                        <Form.Label className="fw-semibold small">{f.label}</Form.Label>
                                                        <Form.Control as="textarea" rows={2} value={f.val} onChange={e => f.set(e.target.value)} disabled={isClosed} />
                                                    </Form.Group>
                                                </Col>
                                            ))}
                                        </Row>
                                        <SaveBar onSave={() => saveStep('D2', {
                                            D1_leader_id: d1Leader || null,
                                            D2_what: d2What, D2_where: d2Where, D2_when: d2When,
                                            D2_who: d2Who, D2_why: d2Why, D2_how: d2How,
                                            D2_how_many: d2HowMany,
                                        })} saving={updateStep.isPending} readonly={isClosed} />
                                    </div>
                                </Tab.Pane>

                                {/* D3 */}
                                <Tab.Pane eventKey="d3">
                                    <div>
                                        <Form.Group className="mb-3">
                                            <Form.Label className="fw-semibold">暫時對策內容</Form.Label>
                                            <Form.Control as="textarea" rows={4} value={d3Action} onChange={e => setD3Action(e.target.value)} disabled={isClosed} />
                                        </Form.Group>
                                        <Row className="mb-3">
                                            <Col md={4}>
                                                <Form.Label className="fw-semibold">生效日期</Form.Label>
                                                <Form.Control type="date" value={d3EffDate} onChange={e => setD3EffDate(e.target.value)} disabled={isClosed} />
                                            </Col>
                                            <Col md={8}>
                                                <Form.Label className="fw-semibold">有效性驗證</Form.Label>
                                                <Form.Control as="textarea" rows={2} value={d3Verif} onChange={e => setD3Verif(e.target.value)} disabled={isClosed} />
                                            </Col>
                                        </Row>
                                        <SaveBar onSave={() => saveStep('D3', {
                                            D3_action: d3Action, D3_effective_date: d3EffDate || null, D3_verification: d3Verif,
                                        })} saving={updateStep.isPending} readonly={isClosed} />
                                    </div>
                                </Tab.Pane>

                                {/* D4 */}
                                <Tab.Pane eventKey="d4">
                                    <div>
                                        <Form.Group className="mb-3">
                                            <Form.Label className="fw-semibold">分析工具</Form.Label>
                                            <div className="d-flex gap-3">
                                                <Form.Check type="radio" id="cara-tool-5why" label="5 Why" value="5why"
                                                    checked={d4Tool === '5why'} onChange={() => setD4Tool('5why')} disabled={isClosed} />
                                                <Form.Check type="radio" id="cara-tool-fishbone" label="魚骨圖（6M）" value="fishbone"
                                                    checked={d4Tool === 'fishbone'} onChange={() => setD4Tool('fishbone')} disabled={isClosed} />
                                            </div>
                                        </Form.Group>
                                        {d4Tool === '5why' ? (
                                            <FiveWhyEditor value={d4FiveWhy} onChange={setD4FiveWhy} readonly={isClosed} />
                                        ) : (
                                            <Row className="g-3">
                                                {['man','machine','material','method','measurement','environment'].map(m => (
                                                    <Col md={4} key={m}>
                                                        <div className="border rounded p-2">
                                                            <div className="fw-semibold small mb-2 text-primary">{m}</div>
                                                            {(d4Fishbone[m] ?? []).map((item, idx) => (
                                                                <div key={idx} className="d-flex gap-1 mb-1">
                                                                    <Form.Control size="sm" value={item}
                                                                        onChange={e => setD4Fishbone(prev => {
                                                                            const arr = [...(prev[m] ?? [])];
                                                                            arr[idx] = e.target.value;
                                                                            return { ...prev, [m]: arr };
                                                                        })} disabled={isClosed} />
                                                                    {!isClosed && (
                                                                        <Button size="sm" variant="outline-danger" onClick={() => setD4Fishbone(prev => ({
                                                                            ...prev, [m]: (prev[m] ?? []).filter((_, i) => i !== idx),
                                                                        }))}>
                                                                            <i className="bi bi-x" />
                                                                        </Button>
                                                                    )}
                                                                </div>
                                                            ))}
                                                            {!isClosed && (
                                                                <Button size="sm" variant="outline-secondary" className="w-100 mt-1"
                                                                    onClick={() => setD4Fishbone(prev => ({ ...prev, [m]: [...(prev[m] ?? []), ''] }))}>
                                                                    <i className="bi bi-plus" /> 新增
                                                                </Button>
                                                            )}
                                                        </div>
                                                    </Col>
                                                ))}
                                            </Row>
                                        )}
                                        <Form.Group className="mt-3">
                                            <Form.Label className="fw-semibold">根本原因（彙整）</Form.Label>
                                            <Form.Control as="textarea" rows={3} value={d4RootCause} onChange={e => setD4RootCause(e.target.value)} disabled={isClosed} />
                                        </Form.Group>
                                        <SaveBar onSave={() => saveStep('D4', {
                                            D4_tool: d4Tool,
                                            D4_five_why: d4Tool === '5why' ? d4FiveWhy : null,
                                            D4_fishbone: d4Tool === 'fishbone' ? d4Fishbone : null,
                                            D4_root_cause: d4RootCause,
                                        })} saving={updateStep.isPending} readonly={isClosed} />
                                    </div>
                                </Tab.Pane>

                                {/* D6 */}
                                <Tab.Pane eventKey="d6">
                                    <div>
                                        <Row className="mb-3">
                                            <Col md={4}>
                                                <Form.Label className="fw-semibold">實施日期</Form.Label>
                                                <Form.Control type="date" value={d6ImplDate} onChange={e => setD6ImplDate(e.target.value)} disabled={isClosed} />
                                            </Col>
                                        </Row>
                                        <Form.Group className="mb-3">
                                            <Form.Label className="fw-semibold">驗證結果</Form.Label>
                                            <Form.Control as="textarea" rows={4} value={d6Result} onChange={e => setD6Result(e.target.value)} disabled={isClosed} />
                                        </Form.Group>
                                        <Form.Check type="switch" id="cara-d6-verified"
                                            label={<span className="fw-semibold text-success">✓ 確認驗證通過（開放 D8 結案）</span>}
                                            checked={d6Verified} onChange={e => setD6Verified(e.target.checked)} disabled={isClosed} className="mb-3" />
                                        {d6Verified && (
                                            <Alert variant="success" className="py-2 small">
                                                <i className="bi bi-check-circle-fill me-2" />D6 驗證已通過，可進行 D8 結案。
                                            </Alert>
                                        )}
                                        <SaveBar onSave={() => saveStep('D6', {
                                            D6_implement_date: d6ImplDate || null, D6_result: d6Result, D6_verified: d6Verified,
                                        })} saving={updateStep.isPending} readonly={isClosed} />
                                    </div>
                                </Tab.Pane>

                                {/* D8 */}
                                <Tab.Pane eventKey="d8">
                                    {isClosed ? (
                                        <Alert variant="success" className="mt-2">
                                            <i className="bi bi-check-circle-fill me-2" />
                                            此 CARA 已於 {cara.D8_close_date ?? '—'} 結案。
                                        </Alert>
                                    ) : (
                                        <div>
                                            {!d6Verified && (
                                                <Alert variant="warning" className="py-2 small">
                                                    <i className="bi bi-exclamation-triangle-fill me-2" />
                                                    D6 尚未勾選「驗證通過」，無法結案。
                                                </Alert>
                                            )}
                                            <Form.Group className="mb-3">
                                                <Form.Label className="fw-semibold">結案確認聲明 <span className="text-danger">*</span></Form.Label>
                                                <Form.Control as="textarea" rows={4} value={d8Confirm} onChange={e => setD8Confirm(e.target.value)} placeholder="請確認所有改善措施均已實施且有效…" />
                                            </Form.Group>
                                            <div className="d-flex justify-content-end">
                                                <Button variant={d6Verified ? 'danger' : 'secondary'}
                                                    disabled={!d6Verified || !d8Confirm.trim() || closeMut.isPending}
                                                    onClick={() => caraId && closeMut.mutate({ id: caraId, D8_confirmation: d8Confirm })}>
                                                    {closeMut.isPending
                                                        ? <><Spinner size="sm" animation="border" className="me-1" />結案中…</>
                                                        : <><i className="bi bi-lock-fill me-1" />確認結案（不可逆）</>
                                                    }
                                                </Button>
                                            </div>
                                        </div>
                                    )}
                                </Tab.Pane>
                            </Tab.Content>
                        </Tab.Container>
                    </>
                )}
            </Modal.Body>

            <Modal.Footer className="justify-content-between">
                <div className="small text-muted">
                    {cara && (
                        <Badge bg={cara.status === '已結案' ? 'success' : 'primary'}>
                            {cara.status}
                        </Badge>
                    )}
                </div>
                <Button variant="secondary" onClick={onHide}>關閉</Button>
            </Modal.Footer>
        </Modal>
    );
};

export default CARAModal;
```

- [ ] **Step 3: 更新 CARAPage 使用新的 caraId prop**

在 `CARAPage.tsx` 中確認 `<CARAModal>` 的呼叫方式與新的 props 相符。
目前 CARAPage 傳入 `show`, `handleClose`, `onSuccess`, `editId` — 需要改成 `show`, `caraId`, `onHide`。

找到 CARAPage.tsx 中 `<CARAModal>` 的使用處，修改為：
```typescript
<CARAModal
    show={showModal}
    caraId={editId}
    onHide={() => { setShowModal(false); setEditId(null); }}
/>
```
並移除 `onSuccess` prop 的傳入（新版 CARAModal 不需要此 prop）。

- [ ] **Step 4: TypeScript 編譯確認**

```bash
cd C:/QC_Database/src_frontend
npm run build 2>&1 | tail -20
```
Expected: 0 errors

- [ ] **Step 5: Commit**

```bash
git add src_frontend/src/hooks/useCARA.ts src_frontend/src/components/cara/CARAModal.tsx src_frontend/src/pages/cara/CARAPage.tsx
git commit -m "feat: 重寫 CARAModal 對接新版 /api/caras/* API，新增 useCARA hooks"
```

---

## Self-Review

### Spec Coverage

| 需求 | 對應任務 |
|------|---------|
| D0-D8 進度條與分頁 | ✅ 已完成（CAPAModal 已有）|
| 5Why 動態 3-7 層 | ✅ 已完成（FiveWhyEditor 已有）|
| 魚骨圖 SVG 渲染 | ⚠️ 目前為表格編輯器（功能完整，非 SVG）|
| D7 橫展任務選擇器 | ✅ 已完成（D7Pane 已有）|
| 連接後端 API | ✅ 已完成 |
| AIAG 8D PDF 報表 | Task 1-3 |
| AIAG 8D Excel 報表 | Task 1,3 |
| PDF/Excel 後端端點 | Task 3 |
| 前端匯出按鈕 | Task 4 |
| 客訴統計圖表頁 | Task 5 |
| 客訴明細開立 CAPA | ✅ 已完成 |
| CARA 前端調整 | Task 6 |
| NCMR 前端開立 CAPA | ✅ 已完成 |

### Type Consistency
- `FiveWhyRow` 在 Task 6 的 useCARA 使用處與 CAPAModal 的定義一致。
- `CARADetail` 中的 `progress.step_status` 鍵使用 `D2`/`D3` 格式，與後端一致。
- `download8DReport` 使用 `api.get` 的 responseType='blob'，與 Axios 型別相符。

### Placeholder Scan
- 無 TBD 或 TODO，所有步驟均有完整程式碼。

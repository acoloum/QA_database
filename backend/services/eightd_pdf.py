"""AIAG 8D 報表 — PDF 格式（reportlab）"""
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# 顏色常數
CLR_DARK_BLUE  = colors.HexColor('#1F4E79')
CLR_MID_BLUE   = colors.HexColor('#2B579A')
CLR_LIGHT_BLUE = colors.HexColor('#D9E1F2')
CLR_GRAY       = colors.HexColor('#808080')

# 字型（嘗試多個路徑，找到就使用 CJK，否則 fallback Helvetica）
_FONT_NAME = 'Helvetica'

def _init_font():
    global _FONT_NAME
    candidates = [
        'C:/Windows/Fonts/msjh.ttc',
        'C:/Windows/Fonts/mingliu.ttc',
        'C:/Windows/Fonts/kaiu.ttf',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont('CJK', path))
                _FONT_NAME = 'CJK'
                return
            except Exception:
                continue

_init_font()


def _fn() -> str:
    return _FONT_NAME


def _ps(size=9, bold=False, color=None, align='left') -> ParagraphStyle:
    """建立 ParagraphStyle"""
    alignment_map = {'left': 0, 'center': 1, 'right': 2}
    kwargs = {
        'fontName': _fn(),
        'fontSize': size,
        'leading':  size + 4,
        'alignment': alignment_map.get(align, 0),
    }
    if bold:
        kwargs['fontName'] = _fn()  # reportlab TTFont 不支援 bold variant，維持同字型
    if color:
        kwargs['textColor'] = color
    return ParagraphStyle(f'ps_{size}_{align}', **kwargs)


def _section_table(title: str, rows: list) -> Table:
    """建立含標題列的雙欄 Table"""
    fn = _fn()
    title_style = _ps(size=10, color=colors.white)
    label_style = _ps(size=9,  color=CLR_DARK_BLUE)
    val_style   = _ps(size=9)

    data = [[Paragraph(title, title_style), '']]
    for label, val in rows:
        data.append([
            Paragraph(str(label), label_style),
            Paragraph(str(val or ''), val_style),
        ])

    col_widths = [50 * mm, 120 * mm]
    t = Table(data, colWidths=col_widths)
    n = len(data)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (1, 0),     CLR_MID_BLUE),
        ('SPAN',          (0, 0), (1, 0)),
        ('FONTNAME',      (0, 0), (1, 0),     fn),
        ('FONTSIZE',      (0, 0), (1, 0),     11),
        ('TOPPADDING',    (0, 0), (-1, -1),   4),
        ('BOTTOMPADDING', (0, 0), (-1, -1),   4),
        ('LEFTPADDING',   (0, 0), (-1, -1),   6),
        ('RIGHTPADDING',  (0, 0), (-1, -1),   6),
        ('BACKGROUND',    (0, 1), (0, n - 1), CLR_LIGHT_BLUE),
        ('GRID',          (0, 0), (-1, -1),   0.5, colors.HexColor('#BBBBBB')),
        ('VALIGN',        (0, 0), (-1, -1),   'TOP'),
    ]))
    return t


def generate_8d_pdf(capa_data: dict) -> BytesIO:
    """從 CAPAService._to_dict() 回傳的 dict 產生 AIAG 8D PDF 報表"""
    buf = BytesIO()
    fn  = _fn()

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

    # ── 封面標題 ──────────────────────────────────────────────
    title_table = Table(
        [[Paragraph('AIAG 8D 問題解決報告', _ps(size=16, color=colors.white))]],
        colWidths=[170 * mm],
    )
    title_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), CLR_DARK_BLUE),
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING',   (0, 0), (-1, -1), 10),
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
        ('Champion',    capa_data.get('D1_champion_name') or ''),
        ('Team Leader', capa_data.get('D1_leader_name') or ''),
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
    if capa_data.get('D4_tool', '5why') == '5why':
        for i, item in enumerate((capa_data.get('D4_five_why') or []), 1):
            if isinstance(item, dict):
                d4_rows.append((f'Why {i}', f"{item.get('why', '')} → {item.get('answer', '')}"))
    else:
        for m_key, items in (capa_data.get('D4_fishbone') or {}).items():
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
        ('實施日期', capa_data.get('D6_implement_date') or ''),
        ('驗證結果', capa_data.get('D6_result') or ''),
        ('驗證通過', '是' if capa_data.get('D6_verified') else '否'),
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
        _ps(size=8, color=CLR_GRAY, align='right'),
    ))

    doc.build(story)
    buf.seek(0)
    return buf

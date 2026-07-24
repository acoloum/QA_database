"""機械性質 Excel 匯入解析：必榮供應商轉置表格式。

來源 Excel 每個工作表對應一種產品尺寸，工作表內每一欄（B欄起）對應一筆檢驗，
A欄為列標籤；本模組將該轉置表解析為與 MechanicalService.create() 相容的 payload。
"""
import re
from datetime import date, datetime
from typing import Any, Optional

# 部分工作表僅以外徑命名（無內徑），與廠商公差主檔的「外徑*內徑」規格對不上；
# 依實際規格補上內徑，使產品尺寸能比對到正確的公差下限（由使用者逐一確認內徑值）。
PRODUCT_SIZE_OVERRIDES: dict[str, str] = {
    "41": "41*35.7",
    "43": "43*35.7",
    "44": "44*36.7",
    "54.5": "54.5*46.2",
    "65": "65*55.7",
    "65.7": "65.7*56.75",
    "78.5": "78.5*69",
    "53": "53*44.2",
    "54": "54*46.35",
    "55": "55*45.7",
    "60": "60*50.6",
    "64.5": "64.5*56.75",
    "66.5": "66.5*56.75",
    "80": "80*70",
    "43.5": "43.5*36.7",
    # 66.7*59 的不同長度變體工作表，公差表僅有 66.7*59 一種內徑，唯一對應可安全補上。
    "66.7X59-1800": "66.7*59",
    "66.7X59-2500": "66.7*59",
}

# Excel 預設產生的通用工作表名稱，實際用途是雜項備用頁，列標籤與其他工作表錯位
# （「成品規格」列實填擠製批號、「重工(N/Y)」列偶爾填尺寸、「擠製日期/批號」列空白），
# 無法可靠解析出正確的產品尺寸，故整張跳過，改由人工個別補建。
SKIPPED_SHEET_NAMES = {"工作表1"}


def normalize_product_size(value: str) -> str:
    """統一產品尺寸的外徑*內徑分隔符號：X／x／× 一律轉為 *（例：80X70 → 80*70）。"""
    if not value:
        return value
    return value.replace("×", "*").replace("X", "*").replace("x", "*")

LABEL_TEST_DATE = "測試日期"
LABEL_EXTRUSION = "擠製日期/批號"
LABEL_T4_FURNACE = "T4爐具編號"
LABEL_T4_TEMP = "T4溫度/時間"
LABEL_T6_TEMP = "T6溫度/時間"
LABEL_REWORK = "重工(N/Y)"
LABEL_NOTE = "備註"

# Excel 列標籤 -> (量測項目, 測量位置, 取樣序)
MEASUREMENT_LABELS: dict[str, tuple[str, str, int]] = {
    "EC 1-1(爐門)": ("EC值", "爐門", 1),
    "EC 1-2(爐門)": ("EC值", "爐門", 2),
    "EC 2-1(爐頂)": ("EC值", "爐頂", 1),
    "EC 2-2(爐頂)": ("EC值", "爐頂", 2),
    "硬度1-1(爐門)": ("硬度", "爐門", 1),
    "硬度1-2(爐門)": ("硬度", "爐門", 2),
    "硬度2-1(爐頂)": ("硬度", "爐頂", 1),
    "硬度2-2(爐頂)": ("硬度", "爐頂", 2),
    "抗拉強度1-1(爐門)": ("抗拉強度", "爐門", 1),
    "抗拉強度1-2(爐門)": ("抗拉強度", "爐門", 2),
    "抗拉強度2-1(爐頂)": ("抗拉強度", "爐頂", 1),
    "抗拉強度2-2(爐頂)": ("抗拉強度", "爐頂", 2),
    "降伏強度1-1(爐門)": ("降伏強度", "爐門", 1),
    "降伏強度1-2(爐門)": ("降伏強度", "爐門", 2),
    "降伏強度2-1(爐頂)": ("降伏強度", "爐頂", 1),
    "降伏強度2-2(爐頂)": ("降伏強度", "爐頂", 2),
    "伸長率1-1(爐門)": ("伸長率", "爐門", 1),
    "伸長率1-2(爐門)": ("伸長率", "爐門", 2),
    "伸長率2-1(爐頂)": ("伸長率", "爐頂", 1),
    "伸長率2-2(爐頂)": ("伸長率", "爐頂", 2),
}


def _row_label_map(ws) -> dict[str, int]:
    """掃描 A 欄，建立標籤 -> 列索引對照（重複標籤僅保留第一個出現的列）。"""
    mapping: dict[str, int] = {}
    for row in range(1, ws.max_row + 1):
        label = ws.cell(row=row, column=1).value
        if isinstance(label, str):
            stripped = label.strip()
            if stripped and stripped not in mapping:
                mapping[stripped] = row
    return mapping


def _t4_furnace_rows(mapping: dict[str, int]) -> list[int]:
    """『擠製日期/批號』列與『T4溫度/時間』列之間的所有列，皆視為 T4爐號候選列。

    來源 Excel 部分工作表在「T4爐具編號」標籤下方多插入一列未標籤的爐號資料
    （同一欄可能同時有兩個 T4 爐號），列位置隨工作表略有偏移，故以標籤間距動態偵測。
    """
    extrusion_row = mapping.get(LABEL_EXTRUSION)
    t4_temp_row = mapping.get(LABEL_T4_TEMP)
    if extrusion_row is None or t4_temp_row is None or t4_temp_row <= extrusion_row + 1:
        furnace_row = mapping.get(LABEL_T4_FURNACE)
        return [furnace_row] if furnace_row else []
    return list(range(extrusion_row + 1, t4_temp_row))


# T4爐號編碼規則：日期(4碼) + 爐次流水號(2碼，可用「/」並列多筆) + T4爐別(T41或T42)
_T4_FURNACE_SPLIT_RE = re.compile(r"^(\d{4})((?:\d{2}/)+\d{2})(T4[12])$", re.IGNORECASE)


def _split_t4_furnace_value(raw: str) -> list[str]:
    """將『日期+爐次流水號(以/分隔多筆)+T4爐別』格式的爐號切分成多筆單一爐號。

    例如 030201/02T42 -> 030201T42、030202T42（同一日期、同一T4爐別，僅流水號不同）。
    不符合此格式（如僅為爐具編號「1號」）則原樣視為單一筆，不強行切分。
    """
    match = _T4_FURNACE_SPLIT_RE.match(raw)
    if not match:
        return [raw]
    date_part, seq_part, suffix = match.groups()
    return [f"{date_part}{seq}{suffix}" for seq in seq_part.split("/")]


def _cell_str(ws, row: Optional[int], col: int) -> Optional[str]:
    if row is None:
        return None
    value = ws.cell(row=row, column=col).value
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cell_date(ws, row: Optional[int], col: int) -> Optional[date]:
    if row is None:
        return None
    value = ws.cell(row=row, column=col).value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _cell_number(ws, row: Optional[int], col: int) -> Optional[float]:
    if row is None:
        return None
    value = ws.cell(row=row, column=col).value
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_payloads_from_workbook(
    wb: Any, material: str, vendor_id: Optional[int]
) -> list[tuple[str, int, dict]]:
    """依必榮機械性質 Excel 轉置表格式，解析出每個工作表、每一欄的檢驗 payload。

    回傳 (工作表名稱, 欄位索引, payload) 清單；欄位全空的欄會被跳過。
    """
    results: list[tuple[str, int, dict]] = []
    for sheet_name in wb.sheetnames:
        if sheet_name.strip() in SKIPPED_SHEET_NAMES:
            continue
        ws = wb[sheet_name]
        if ws.max_column < 2:
            continue
        mapping = _row_label_map(ws)
        if LABEL_EXTRUSION not in mapping and LABEL_TEST_DATE not in mapping:
            continue

        sheet_key = sheet_name.strip()
        product_size = normalize_product_size(
            PRODUCT_SIZE_OVERRIDES.get(sheet_key, sheet_key)
        )
        furnace_rows = _t4_furnace_rows(mapping)
        measurement_rows = {
            key: mapping[label]
            for label, key in MEASUREMENT_LABELS.items()
            if label in mapping
        }

        for col in range(2, ws.max_column + 1):
            test_date = _cell_date(ws, mapping.get(LABEL_TEST_DATE), col)
            extrusion_value = _cell_str(ws, mapping.get(LABEL_EXTRUSION), col)
            furnace_values: list[str] = []
            for row in furnace_rows:
                raw = _cell_str(ws, row, col)
                if raw is not None:
                    furnace_values.extend(_split_t4_furnace_value(raw))
            t4_temp = _cell_str(ws, mapping.get(LABEL_T4_TEMP), col)
            t6_temp = _cell_str(ws, mapping.get(LABEL_T6_TEMP), col)
            rework = _cell_str(ws, mapping.get(LABEL_REWORK), col)
            note = _cell_str(ws, mapping.get(LABEL_NOTE), col)

            measurements = []
            for (item, location, sample_no), row in measurement_rows.items():
                value = _cell_number(ws, row, col)
                if value is not None:
                    measurements.append({
                        "量測項目": item,
                        "測量位置": location,
                        "取樣序": sample_no,
                        "量測值": value,
                    })

            has_data = any([
                test_date, extrusion_value, furnace_values, t4_temp, t6_temp,
                rework, note, measurements,
            ])
            if not has_data:
                continue

            final_note = note
            if rework and rework.strip().upper() == "Y":
                final_note = f"[重工] {note}" if note else "[重工]"

            payload = {
                "產品尺寸": product_size,
                "材質": material,
                "廠商ID": vendor_id,
                "測試日期": test_date.isoformat() if test_date else None,
                "T4溫度時間": t4_temp,
                "T6溫度時間": t6_temp,
                "備註": final_note,
                "extrusion_numbers": (
                    [{"序號": 1, "編號": extrusion_value}] if extrusion_value else []
                ),
                "t4_furnace_numbers": [
                    {"序號": i + 1, "編號": value}
                    for i, value in enumerate(furnace_values)
                ],
                "measurements": measurements,
            }
            results.append((sheet_name, col, payload))
    return results

"""MSA 正式報告：只讀已保存的結果版本，絕不重新分析。

報告的價值在於「當時的證據長什麼樣」，因此所有內容都來自結果版本
自己保存的快照；設備改名、準則改版或觀測後續修正，都不會改變已
產生的報告。
"""

from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from ..extensions import db
from ..models import MsaResultVersion, MsaWorkflowDecision, User
from .msa_errors import MsaNotFound, MsaValidationError


SHEET_NAMES = (
    "研究摘要", "研究設計", "原始讀值", "統計結果",
    "圖表資料", "設備與校驗", "準則與判定", "核准歷程", "版本稽核",
)

# 尚未核准的結果必須在報告上明確標示，避免被當成正式結論引用
UNAPPROVED_NOTICE = "草稿／未核准：本報告尚未完成核准，不得作為正式判定依據"

_HEADER_FILL = PatternFill("solid", fgColor="1F3B39")
_HEADER_FONT = Font(color="FFFFFF", bold=True)
_TITLE_FONT = Font(bold=True, size=14)
_WARNING_FONT = Font(color="A63440", bold=True)

_DISPOSITION_LABELS = {
    "acceptable": "可接受",
    "conditionally_acceptable": "條件接受",
    "unacceptable": "不可接受",
    "indeterminate": "無法判定",
}


class MsaReportService:
    """由不可變結果版本產生可稽核的報告檔。"""

    @staticmethod
    def generate_excel(result_version_id: int) -> BytesIO:
        snapshot = MsaReportService._load_snapshot(result_version_id)
        workbook = Workbook()
        workbook.remove(workbook.active)
        for name in SHEET_NAMES:
            workbook.create_sheet(name)

        MsaReportService._write_summary(workbook["研究摘要"], snapshot)
        MsaReportService._write_design(workbook["研究設計"], snapshot)
        MsaReportService._write_observations(workbook["原始讀值"], snapshot)
        MsaReportService._write_statistics(workbook["統計結果"], snapshot)
        MsaReportService._write_charts(workbook["圖表資料"], snapshot)
        MsaReportService._write_equipment(workbook["設備與校驗"], snapshot)
        MsaReportService._write_criteria(workbook["準則與判定"], snapshot)
        MsaReportService._write_workflow(workbook["核准歷程"], snapshot)
        MsaReportService._write_audit(workbook["版本稽核"], snapshot)

        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        return output

    # ------------------------------------------------------------------
    # 快照載入
    # ------------------------------------------------------------------

    @staticmethod
    def _load_snapshot(result_version_id: int) -> dict:
        result = db.session.get(MsaResultVersion, result_version_id)
        if result is None:
            raise MsaNotFound(
                "MSA_RESULT_NOT_FOUND",
                "找不到 MSA 結果版本",
                details={"result_version_id": result_version_id},
            )

        summary = result.raw_data_summary or {}
        missing = [
            key for key in ("study", "plan", "effective_observations")
            if not summary.get(key)
        ]
        if missing:
            raise MsaValidationError(
                "MSA_REPORT_EVIDENCE_INCOMPLETE",
                "結果版本缺少完整證據快照，且不得回頭重算",
                details={"missing": missing},
            )

        return {
            "result": result,
            "study": summary["study"],
            "plan": summary["plan"],
            "observations": summary["effective_observations"],
            "method": summary.get("method") or {},
            "statistics": result.statistics or {},
            "charts": result.chart_data or {},
            "criteria": result.criteria_snapshot or {},
            "conclusion": result.conclusion or {},
            "warnings": result.warnings or [],
            "blockers": result.blockers or [],
            "workflow": MsaReportService._serialize_decisions(result),
        }

    @staticmethod
    def _serialize_decisions(result: MsaResultVersion) -> list[dict]:
        decisions = (
            MsaWorkflowDecision.query
            .filter_by(study_id=result.study_id)
            .order_by(MsaWorkflowDecision.id.asc())
            .all()
        )
        actor_names = {
            user.id: user.username
            for user in User.query.filter(
                User.id.in_({row.actor_id for row in decisions} or {0})
            ).all()
        }
        return [
            {
                "action": row.action,
                "from_status": row.from_status,
                "to_status": row.to_status,
                "reason": row.reason,
                "actor_id": row.actor_id,
                "actor": actor_names.get(row.actor_id),
                "created_at": (
                    row.created_at.isoformat() if row.created_at else None
                ),
                "separation_check": row.separation_check or {},
                "extra_data": row.extra_data or {},
            }
            for row in decisions
        ]

    # ------------------------------------------------------------------
    # 工作表
    # ------------------------------------------------------------------

    @staticmethod
    def _write_summary(sheet, snapshot) -> None:
        result = snapshot["result"]
        study = snapshot["study"]
        conclusion = snapshot["conclusion"]

        sheet["A1"] = "MSA 量測系統分析報告"
        sheet["A1"].font = _TITLE_FONT
        row = 3
        if result.status != "approved":
            sheet.cell(row=row, column=1, value=UNAPPROVED_NOTICE).font = (
                _WARNING_FONT
            )
            row += 2

        pairs = [
            ("研究編號", study.get("study_no")),
            ("研究類型", study.get("study_type")),
            ("量測目的", study.get("measurement_purpose")),
            ("品質特性", study.get("characteristic")),
            ("單位", study.get("unit")),
            ("規格下限", _number(study.get("lsl"))),
            ("規格上限", _number(study.get("usl"))),
            ("結果狀態", result.status),
            ("系統處置", _DISPOSITION_LABELS.get(
                conclusion.get("system_disposition"),
                conclusion.get("system_disposition"),
            )),
            ("百分比口徑", conclusion.get("percent_basis")),
            ("工程判斷", conclusion.get("engineering_judgment") or "未附加"),
        ]
        row = _write_pairs(sheet, pairs, start_row=row)

        row += 1
        sheet.cell(row=row, column=1, value="判定理由").font = _HEADER_FONT
        sheet.cell(row=row, column=1).fill = _HEADER_FILL
        for reason in conclusion.get("reasons") or []:
            row += 1
            sheet.cell(row=row, column=1, value=_safe(reason))
        for item in snapshot["blockers"]:
            row += 1
            sheet.cell(
                row=row, column=1,
                value=_safe(f"阻擋：{item.get('message')}"),
            ).font = _WARNING_FONT
        for item in snapshot["warnings"]:
            row += 1
            sheet.cell(row=row, column=1, value=_safe(f"警告：{item.get('message')}"))
        _autosize(sheet)

    @staticmethod
    def _write_design(sheet, snapshot) -> None:
        plan = snapshot["plan"]
        row = _write_pairs(sheet, [
            ("計畫版本號", plan.get("plan_version_no")),
            ("方法代碼", plan.get("method_code")),
            ("方法版本", plan.get("method_version")),
            ("設計型態", plan.get("design_type")),
            ("零件數", plan.get("part_count")),
            ("評價人數", plan.get("appraiser_count")),
            ("試驗次數", plan.get("trial_count")),
            ("隨機種子", plan.get("random_seed")),
            ("計畫雜湊", plan.get("plan_hash")),
            ("凍結時間", plan.get("frozen_at")),
        ], start_row=1)

        row += 2
        _write_table(
            sheet,
            headers=("零件序號", "盲碼", "零件識別", "參考值", "參考分類"),
            rows=[
                (
                    part.get("part_no"), part.get("blind_code"),
                    _safe(part.get("part_identifier")),
                    _number(part.get("reference_value")),
                    _safe(part.get("reference_category")),
                )
                for part in plan.get("parts") or []
            ],
            start_row=row,
        )
        row += len(plan.get("parts") or []) + 3
        _write_table(
            sheet,
            headers=("評價人序號", "盲碼", "姓名"),
            rows=[
                (
                    row_data.get("appraiser_no"), row_data.get("blind_code"),
                    _safe(row_data.get("name")),
                )
                for row_data in plan.get("appraisers") or []
            ],
            start_row=row,
        )
        _autosize(sheet)

    @staticmethod
    def _write_observations(sheet, snapshot) -> None:
        """原始讀值直接來自結果快照，不重新查詢目前有效觀測。"""
        _write_table(
            sheet,
            headers=(
                "要求順序", "實際輸入順序", "零件盲碼", "評價人盲碼",
                "試驗次數", "計量讀值", "計數分類", "量測時間", "來源",
            ),
            rows=[
                (
                    row.get("requested_order"), row.get("actual_entry_order"),
                    row.get("part_blind_code"), row.get("appraiser_blind_code"),
                    row.get("trial_no"), _number(row.get("numeric_value")),
                    _safe(row.get("attribute_value")),
                    _safe(row.get("measured_at")), row.get("source"),
                )
                for row in snapshot["observations"]
            ],
            start_row=1,
            freeze=True,
            autofilter=True,
        )
        _autosize(sheet)

    @staticmethod
    def _write_statistics(sheet, snapshot) -> None:
        rows = []
        _flatten(snapshot["statistics"], "", rows)
        _write_table(
            sheet,
            headers=("統計項目", "值"),
            rows=[(_safe(path), _cell(value)) for path, value in rows],
            start_row=1,
            freeze=True,
            autofilter=True,
        )
        _autosize(sheet)

    @staticmethod
    def _write_charts(sheet, snapshot) -> None:
        """保存畫面實際使用的 series，報告與畫面必須是同一份數字。"""
        rows = []
        _flatten(snapshot["charts"], "", rows)
        _write_table(
            sheet,
            headers=("圖表資料路徑", "值"),
            rows=[(_safe(path), _cell(value)) for path, value in rows],
            start_row=1,
            freeze=True,
            autofilter=True,
        )
        _autosize(sheet)

    @staticmethod
    def _write_equipment(sheet, snapshot) -> None:
        equipment = (snapshot["plan"].get("equipment_snapshot") or {})
        items = equipment.get("items") or []
        row = _write_pairs(sheet, [
            ("資格檢查日", equipment.get("checked_on")),
            (
                "解析度評估",
                (equipment.get("resolution_assessment") or {}).get("level"),
            ),
            (
                "評估說明",
                (equipment.get("resolution_assessment") or {}).get("reason"),
            ),
        ], start_row=1)

        row += 2
        _write_table(
            sheet,
            headers=(
                "角色", "量測模式", "設備編號", "設備名稱", "狀態",
                "解析度", "單位", "校驗結果", "下次校驗日",
            ),
            rows=[
                (
                    item.get("role"), item.get("measurement_mode"),
                    _safe(item.get("equipment_no")), _safe(item.get("name")),
                    item.get("status"), _number(item.get("resolution")),
                    _safe(item.get("unit")),
                    _safe((item.get("calibration") or {}).get("result")),
                    _safe((item.get("calibration") or {}).get("next_due_date")),
                )
                for item in items
            ],
            start_row=row,
        )
        _autosize(sheet)

    @staticmethod
    def _write_criteria(sheet, snapshot) -> None:
        criteria = snapshot["criteria"]
        row = _write_pairs(sheet, [
            ("準則設定", _safe(criteria.get("profile_name"))),
            ("準則版本ID", criteria.get("version_id")),
            ("準則版本號", criteria.get("version_no")),
            ("方法版本", _safe(criteria.get("method_version"))),
            ("生效日", _safe(criteria.get("effective_date"))),
            ("百分比口徑", criteria.get("percent_basis")),
            ("口徑來源", criteria.get("percent_basis_source")),
            ("依據", _safe(criteria.get("basis"))),
        ], start_row=1)

        row += 2
        _write_table(
            sheet,
            headers=("門檻", "值"),
            rows=[
                (_safe(key), _cell(value))
                for key, value in sorted(
                    (criteria.get("thresholds") or {}).items()
                )
            ],
            start_row=row,
        )
        row += len(criteria.get("thresholds") or {}) + 3
        _write_table(
            sheet,
            headers=("條件接受必要措施",),
            rows=[
                (_safe(action),)
                for action in criteria.get("conditional_actions") or []
            ],
            start_row=row,
        )
        _autosize(sheet)

    @staticmethod
    def _write_workflow(sheet, snapshot) -> None:
        _write_table(
            sheet,
            headers=(
                "動作", "原狀態", "新狀態", "執行者", "執行者ID",
                "時間", "理由", "職責分離檢查",
            ),
            rows=[
                (
                    row.get("action"), row.get("from_status"),
                    row.get("to_status"), _safe(row.get("actor")),
                    row.get("actor_id"), _safe(row.get("created_at")),
                    _safe(row.get("reason")),
                    _safe(_compact(row.get("separation_check"))),
                )
                for row in snapshot["workflow"]
            ],
            start_row=1,
            freeze=True,
            autofilter=True,
        )
        _autosize(sheet)

    @staticmethod
    def _write_audit(sheet, snapshot) -> None:
        result = snapshot["result"]
        _write_pairs(sheet, [
            ("結果版本ID", result.id),
            ("結果版本號", result.result_version_no),
            ("研究ID", result.study_id),
            ("計畫版本ID", result.plan_version_id),
            ("資料雜湊", result.data_hash),
            ("方法代碼", result.method_code),
            ("方法版本", result.method_version),
            ("程式版本", result.code_version),
            ("結果狀態", result.status),
            ("建立者ID", result.created_by_id),
            (
                "建立時間",
                result.created_at.isoformat() if result.created_at else None,
            ),
        ], start_row=1)
        _autosize(sheet)


# ----------------------------------------------------------------------
# 共用寫入
# ----------------------------------------------------------------------


def _safe(value):
    """避免試算表把使用者文字當公式執行。"""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _number(value):
    """數值保留原精度，不先轉成顯示字串。"""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float, Decimal)):
        return value
    try:
        return float(Decimal(str(value)))
    except Exception:
        return _safe(value)


def _cell(value):
    if isinstance(value, (dict, list, tuple)):
        return _safe(_compact(value))
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float, Decimal)):
        return value
    return _safe(str(value))


def _compact(value) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _flatten(value, prefix: str, rows: list) -> None:
    """把巢狀統計輸出攤平成可稽核的路徑／值配對。"""
    if isinstance(value, dict):
        for key in sorted(value, key=str):
            _flatten(value[key], f"{prefix}.{key}" if prefix else str(key), rows)
        return
    if isinstance(value, (list, tuple)):
        if value and all(
            not isinstance(item, (dict, list, tuple)) for item in value
        ):
            rows.append((prefix, _compact(list(value))))
            return
        for index, item in enumerate(value):
            _flatten(item, f"{prefix}[{index}]", rows)
        return
    rows.append((prefix, value))


def _write_pairs(sheet, pairs, *, start_row: int) -> int:
    row = start_row
    for label, value in pairs:
        sheet.cell(row=row, column=1, value=label).font = Font(bold=True)
        sheet.cell(row=row, column=2, value=_cell(value))
        row += 1
    return row


def _write_table(
    sheet, *, headers, rows, start_row: int,
    freeze: bool = False, autofilter: bool = False,
) -> None:
    for index, header in enumerate(headers, start=1):
        cell = sheet.cell(row=start_row, column=index, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(vertical="center")
    for offset, values in enumerate(rows, start=1):
        for index, value in enumerate(values, start=1):
            sheet.cell(row=start_row + offset, column=index, value=value)
    if autofilter and rows:
        last_column = get_column_letter(len(headers))
        sheet.auto_filter.ref = (
            f"A{start_row}:{last_column}{start_row + len(rows)}"
        )
    if freeze:
        sheet.freeze_panes = sheet.cell(row=start_row + 1, column=1)


def _autosize(sheet) -> None:
    widths = {}
    for row in sheet.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            length = min(len(str(cell.value)), 60)
            widths[cell.column] = max(widths.get(cell.column, 10), length + 2)
    for column, width in widths.items():
        sheet.column_dimensions[get_column_letter(column)].width = width

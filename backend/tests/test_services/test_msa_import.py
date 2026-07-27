"""設備 CSV 受控匯入服務的回歸測試。"""

from datetime import date
from io import BytesIO
from pathlib import Path

import pytest
from sqlalchemy.exc import DataError

import backend.services.msa_import_service as msa_import_module
from backend.models import (
    AuditLog,
    EquipmentImportBatch,
    EquipmentImportRow,
    MeasurementEquipment,
)
from backend.services.msa_errors import MsaConflict, MsaValidationError
from backend.services.msa_import_service import (
    MAX_COLUMNS,
    MAX_FILE_BYTES,
    MAX_ROWS,
    PARSER_VERSION,
    MsaImportService,
    inspect_equipment_csv,
    normalize_equipment_row,
)


FIXTURE_PATH = (
    Path(__file__).parents[1] / "fixtures" / "msa_equipment_import.csv"
)


def _preview(actor_id=1):
    return MsaImportService.preview(
        FIXTURE_PATH,
        "equipment.csv",
        actor_id=actor_id,
        as_of=date(2026, 7, 27),
    )


def _preview_content(content: str, *, actor_id=1):
    return MsaImportService.preview(
        BytesIO(content.encode("utf-8-sig")),
        "equipment.csv",
        actor_id=actor_id,
        as_of=date(2026, 7, 27),
    )


def test_parser_limits_are_fixed_by_the_import_contract():
    """誤改解析器版本或放寬資源上限時，此測試應失敗。"""
    assert PARSER_VERSION == "msa-equipment-csv-1"
    assert MAX_FILE_BYTES == 5 * 1024 * 1024
    assert MAX_ROWS == 5000
    assert MAX_COLUMNS == 50


def test_normalize_cleans_html_and_keeps_raw_source():
    """若把 HTML 原值覆寫或交給前端直接渲染，此測試應失敗。"""
    raw = {
        "設備編號": "EQ-9",
        "名稱": "測試量具",
        "狀態": "使用中",
        "類別": "外校",
        "效準提醒": '<span class="danger">校驗即將到期</span>',
        "備註": "送校，S/N: ABC123",
        "解析度": "0.01",
        "單位": "mm",
    }

    normalized = normalize_equipment_row(
        raw,
        source_row_no=2,
        as_of=date(2026, 7, 27),
    )

    assert normalized.data["status"] == "active"
    assert normalized.data["reminder_text"] == "校驗即將到期"
    assert normalized.data["serial_no"] == "ABC123"
    assert normalized.data["legacy_notes"] == "送校，S/N: ABC123"
    assert raw["效準提醒"].startswith("<span")


@pytest.mark.parametrize(
    "reminder",
    [
        "&lt;img src=x onerror=alert(1)&gt;校驗即將到期",
        "&amp;lt;img src=x onerror=alert(1)&amp;gt;校驗即將到期",
    ],
)
def test_html_cleaning_decodes_entities_before_extracting_plain_text(reminder):
    """encoded 或 double-encoded markup 若流入輸出，此測試應失敗。"""
    normalized = normalize_equipment_row(
        {
            "設備編號": "EQ-HTML",
            "名稱": "測試量具",
            "效準提醒": reminder,
        },
        source_row_no=2,
        as_of=date(2026, 7, 27),
    )

    assert normalized.data["reminder_text"] == "校驗即將到期"
    assert "<" not in normalized.data["reminder_text"]
    assert "onerror" not in normalized.data["reminder_text"]
    assert normalized.html_cleaned is True


def test_plain_entity_decode_does_not_count_as_html_cleaning():
    """純文字 entity 若被誤算成 HTML 清理列，此測試應失敗。"""
    normalized = normalize_equipment_row(
        {
            "設備編號": "EQ-TEXT",
            "名稱": "測試量具",
            "效準提醒": "AT&amp;T 校驗",
        },
        source_row_no=2,
        as_of=date(2026, 7, 27),
    )

    assert normalized.data["reminder_text"] == "AT&T 校驗"
    assert normalized.html_cleaned is False


@pytest.mark.parametrize(
    "resolution",
    [
        "1e100000",
        "1e-100000",
        "9999999999999999999999999999999999999999",
        "1000001",
        "0.0000000000001",
    ],
)
def test_resolution_rejects_unbounded_decimal_without_expansion(resolution):
    """超長、極端指數或超出業務範圍的解析度不得展開成巨量字串。"""
    normalized = normalize_equipment_row(
        {
            "設備編號": "EQ-DECIMAL",
            "名稱": "測試量具",
            "狀態": "使用中",
            "類別": "外校",
            "解析度": resolution,
            "單位": "mm",
            "型號": "M-1",
            "操作者": "測試人員",
        },
        source_row_no=2,
        as_of=date(2026, 7, 27),
    )

    assert normalized.data["resolution"] is None
    assert "MSA_IMPORT_RESOLUTION_INVALID" in normalized.issue_codes


def test_serial_requires_supported_prefix_and_preserves_review_candidates():
    """若將 NO 或空 SN 猜成正式序號，或漏掉人工候選，此測試應失敗。"""
    empty_sn = normalize_equipment_row(
        {"設備編號": "EQ-1", "名稱": "量具", "備註": "SN：內側爪補正值：+0.04"},
        source_row_no=49,
        as_of=date(2026, 7, 27),
    )
    unsupported_no = normalize_equipment_row(
        {"設備編號": "EQ-2", "名稱": "量具", "備註": "(NO：6543)"},
        source_row_no=97,
        as_of=date(2026, 7, 27),
    )

    assert empty_sn.data["serial_no"] is None
    assert "MSA_IMPORT_SERIAL_PREFIX_WITHOUT_VALUE" in empty_sn.issue_codes
    assert empty_sn.serial_review_candidate is True
    assert unsupported_no.data["serial_no"] is None
    assert "MSA_IMPORT_SERIAL_UNSUPPORTED_PREFIX" in unsupported_no.issue_codes
    assert unsupported_no.serial_review_candidate is True


def test_ambiguous_calibration_type_requires_confirmation():
    """若把「遊校」自行映射成內校或外校，此測試應失敗。"""
    normalized = normalize_equipment_row(
        {"設備編號": "EQ-4", "名稱": "量具", "校驗類別": "遊校"},
        source_row_no=4,
        as_of=date(2026, 7, 27),
    )

    assert normalized.data["calibration_type"] is None
    assert (
        "MSA_IMPORT_AMBIGUOUS_CALIBRATION_TYPE"
        in normalized.issue_codes
    )


def test_fixture_statistics_are_independently_reproducible():
    """解析漏列、信任來源逾期旗標或誤算候選時，此測試應失敗。"""
    result = inspect_equipment_csv(
        FIXTURE_PATH.read_bytes(),
        as_of=date(2026, 7, 27),
    )

    assert result.statistics == {
        "total_rows": 6,
        "status_counts": {
            "active": 4,
            "maintenance": 1,
            "scrapped": 1,
        },
        "serial_review_candidates": 3,
        "serials_auto_extracted": 2,
        "html_cleaned_rows": 1,
        "ambiguous_calibration_rows": 1,
        "active_expired_rows": 1,
    }


def test_preview_normalizes_without_creating_equipment(db_session):
    """preview 若提早建立正式設備或漏存 raw/normalized，此測試應失敗。"""
    batch = _preview()

    assert batch.status == "previewed"
    assert MeasurementEquipment.query.count() == 0
    rows = (
        EquipmentImportRow.query.filter_by(batch_id=batch.id)
        .order_by(EquipmentImportRow.row_number)
        .all()
    )
    assert len(rows) == 6
    assert rows[0].normalized_data["status"] == "active"
    assert "<span" not in rows[0].normalized_data["reminder_text"]
    assert "<span" in rows[0].raw_data["效準提醒"]
    assert rows[0].normalized_data["serial_no"] == "DEMO-A01"


def test_preview_is_idempotent_for_same_sha(db_session):
    """同一 SHA 若建立第二批或重複 rows，此測試應失敗。"""
    first = _preview()
    second = _preview(actor_id=2)

    assert second.id == first.id
    assert EquipmentImportBatch.query.count() == 1
    assert EquipmentImportRow.query.count() == 6


@pytest.mark.parametrize(
    ("filename", "content", "code"),
    [
        ("equipment.txt", b"a,b\n1,2\n", "MSA_IMPORT_FILE_TYPE_INVALID"),
        ("equipment.csv", b"", "MSA_IMPORT_FILE_EMPTY"),
    ],
)
def test_preview_rejects_invalid_file_before_writing_batch(
    db_session,
    filename,
    content,
    code,
):
    """副檔名或空檔驗證失效、留下半批資料時，此測試應失敗。"""
    with pytest.raises(MsaValidationError) as error:
        MsaImportService.preview(
            BytesIO(content),
            filename,
            actor_id=1,
            as_of=date(2026, 7, 27),
        )

    assert error.value.code == code
    assert EquipmentImportBatch.query.count() == 0


def test_csv_parser_enforces_size_row_and_column_limits(monkeypatch):
    """任一資源上限只宣告未實際執行時，此測試應失敗。"""
    monkeypatch.setattr(msa_import_module, "MAX_FILE_BYTES", 20)
    with pytest.raises(MsaValidationError) as too_large:
        inspect_equipment_csv(
            b"\xe8\xa8\xad\xe5\x82\x99\xe7\xb7\xa8\xe8\x99\x9f,\xe5\x90\x8d\xe7\xa8\xb1\n"
            b"EQ-1,Gauge\n",
            as_of=date(2026, 7, 27),
        )
    assert too_large.value.code == "MSA_IMPORT_FILE_TOO_LARGE"

    monkeypatch.setattr(msa_import_module, "MAX_FILE_BYTES", MAX_FILE_BYTES)
    monkeypatch.setattr(msa_import_module, "MAX_COLUMNS", 2)
    with pytest.raises(MsaValidationError) as too_wide:
        inspect_equipment_csv(
            "設備編號,名稱,狀態\nEQ-1,量具,使用中\n".encode(),
            as_of=date(2026, 7, 27),
        )
    assert too_wide.value.code == "MSA_IMPORT_COLUMN_LIMIT_EXCEEDED"

    monkeypatch.setattr(msa_import_module, "MAX_COLUMNS", MAX_COLUMNS)
    monkeypatch.setattr(msa_import_module, "MAX_ROWS", 1)
    with pytest.raises(MsaValidationError) as too_many:
        inspect_equipment_csv(
            "設備編號,名稱\nEQ-1,量具一\nEQ-2,量具二\n".encode(),
            as_of=date(2026, 7, 27),
        )
    assert too_many.value.code == "MSA_IMPORT_ROW_LIMIT_EXCEEDED"


def test_csv_parser_accepts_cp950_without_changing_source_bytes():
    """移除 CP950 fallback 時，此測試應失敗。"""
    content = "設備編號,名稱\nEQ-1,游標卡尺\n".encode("cp950")

    inspection = inspect_equipment_csv(
        content,
        as_of=date(2026, 7, 27),
    )

    assert inspection.encoding == "cp950"
    assert inspection.rows[0][1].data["name"] == "游標卡尺"


@pytest.mark.parametrize("control_character", ["\x00", "\x01", "\x7f"])
def test_csv_parser_rejects_disallowed_control_characters(
    control_character,
):
    """U+0000 或其他不允許控制字元若進入 raw JSON，此測試應失敗。"""
    content = (
        f"設備編號,名稱\nEQ-1,游標{control_character}卡尺\n"
    ).encode("utf-8")

    with pytest.raises(MsaValidationError) as error:
        inspect_equipment_csv(content, as_of=date(2026, 7, 27))

    assert error.value.code == "MSA_IMPORT_CONTROL_CHARACTER_INVALID"


def test_preview_converts_database_data_error_to_stable_validation(
    db_session,
    monkeypatch,
):
    """資料庫拒絕 preview 值時，不得洩漏 DataError 或留下半批資料。"""
    def fail_flush():
        raise DataError("INSERT", {}, ValueError("invalid data"))

    monkeypatch.setattr(db_session, "flush", fail_flush)

    with pytest.raises(MsaValidationError) as error:
        _preview()

    assert error.value.code == "MSA_IMPORT_DATABASE_VALUE_INVALID"
    assert EquipmentImportBatch.query.count() == 0


def test_confirm_keeps_unresolved_rows_pending_and_accepts_valid_resolution(
    db_session,
):
    """若歧義列靜默成 active，或有效人工映射未生效，此測試應失敗。"""
    batch = _preview()
    rows = {
        row.normalized_data["equipment_no"]: row
        for row in EquipmentImportRow.query.filter_by(batch_id=batch.id)
    }

    confirmed = MsaImportService.confirm(
        batch.id,
        actor_id=1,
        resolutions={
            str(rows["EQ-TEST-005"].id): {
                "action": "accept",
                "calibration_type": "external",
            },
            str(rows["EQ-TEST-006"].id): {"action": "pending_review"},
        },
        confirmation_date=date(2026, 7, 27),
    )

    ambiguous = MeasurementEquipment.query.filter_by(
        equipment_no="EQ-TEST-005"
    ).one()
    unsupported = MeasurementEquipment.query.filter_by(
        equipment_no="EQ-TEST-006"
    ).one()
    assert confirmed.status == "confirmed"
    assert ambiguous.calibration_type == "external"
    assert ambiguous.status == "active"
    assert unsupported.serial_no is None
    assert unsupported.status == "pending_review"
    assert confirmed.success_rows == 6
    assert confirmed.pending_rows == 1
    audit = AuditLog.query.filter_by(
        module="msa_equipment_import",
        action="confirm",
        record_id=batch.id,
    ).one()
    assert audit.new_value["resolutions"] == {
        str(rows["EQ-TEST-005"].id): {
            "action": "accept",
            "calibration_type": "external",
        },
        str(rows["EQ-TEST-006"].id): {
            "action": "pending_review",
        },
    }


def test_confirm_recomputes_expiry_from_confirmation_date(db_session):
    """若 confirm 信任 preview 或來源逾期旗標，此測試應失敗。"""
    batch = MsaImportService.preview(
        FIXTURE_PATH,
        "equipment.csv",
        actor_id=1,
        as_of=date(2026, 1, 1),
    )
    row = next(
        item
        for item in EquipmentImportRow.query.filter_by(batch_id=batch.id)
        if item.normalized_data["equipment_no"] == "EQ-TEST-002"
    )
    assert row.normalized_data["is_expired"] is False

    MsaImportService.confirm(
        batch.id,
        actor_id=1,
        resolutions={},
        confirmation_date=date(2026, 7, 27),
    )

    db_session.refresh(row)
    assert row.normalized_data["is_expired"] is True


def test_exempt_resolution_requires_reason_in_same_resolution(db_session):
    """將遊校映射 exempt 卻沒有理由時，不得產生 active + NULL 類別。"""
    batch = _preview_content(
        "設備編號,名稱,狀態,類別,型號,操作者,解析度,單位\n"
        "EQ-EXEMPT,測試量具,使用中,遊校,M-1,測試人員,0.01,mm\n"
    )
    row = EquipmentImportRow.query.filter_by(batch_id=batch.id).one()

    with pytest.raises(MsaValidationError) as error:
        MsaImportService.confirm(
            batch.id,
            actor_id=1,
            resolutions={
                str(row.id): {
                    "action": "accept",
                    "calibration_type": "exempt",
                }
            },
            confirmation_date=date(2026, 7, 27),
        )

    assert error.value.code == "MSA_IMPORT_RESOLUTION_INVALID"
    assert MeasurementEquipment.query.count() == 0
    db_session.expire_all()
    assert db_session.get(EquipmentImportBatch, batch.id).status == "previewed"


def test_switching_away_from_exempt_clears_stale_exemption_issue(db_session):
    """免校改映射外校後，舊豁免理由 issue 不得讓設備停在 pending。"""
    batch = _preview_content(
        "設備編號,名稱,狀態,類別,型號,操作者,解析度,單位\n"
        "EQ-EXEMPT,測試量具,使用中,免校,M-1,測試人員,0.01,mm\n"
    )
    row = EquipmentImportRow.query.filter_by(batch_id=batch.id).one()

    MsaImportService.confirm(
        batch.id,
        actor_id=1,
        resolutions={
            str(row.id): {
                "action": "accept",
                "calibration_type": "external",
            }
        },
        confirmation_date=date(2026, 7, 27),
    )

    equipment = MeasurementEquipment.query.filter_by(
        equipment_no="EQ-EXEMPT"
    ).one()
    db_session.refresh(row)
    assert equipment.status == "active"
    assert equipment.calibration_type == "external"
    assert (
        "MSA_IMPORT_EXEMPTION_REASON_MISSING"
        not in row.normalized_data["unresolved_issue_codes"]
    )


def test_rejected_existing_number_does_not_block_other_rows(db_session):
    """reject 的既有編號若仍進 duplicate precheck，此測試應失敗。"""
    batch = _preview_content(
        "設備編號,名稱,狀態,類別,型號,操作者,解析度,單位\n"
        "EQ-OLD,既有量具,使用中,外校,M-1,測試人員,0.01,mm\n"
        "EQ-NEW,新量具,使用中,外校,M-2,測試人員,0.01,mm\n"
    )
    rows = {
        row.normalized_data["equipment_no"]: row
        for row in EquipmentImportRow.query.filter_by(batch_id=batch.id)
    }
    db_session.add(
        MeasurementEquipment(
            equipment_no="EQ-OLD",
            name="資料庫既有設備",
            status="pending_review",
        )
    )
    db_session.commit()

    confirmed = MsaImportService.confirm(
        batch.id,
        actor_id=1,
        resolutions={
            str(rows["EQ-OLD"].id): {"action": "reject"},
        },
        confirmation_date=date(2026, 7, 27),
    )

    assert confirmed.success_rows == 1
    assert confirmed.rejected_rows == 1
    assert MeasurementEquipment.query.filter_by(
        equipment_no="EQ-NEW"
    ).count() == 1


def test_confirm_is_idempotent_and_writes_one_batch_audit(db_session):
    """重複 confirm 若建立重複設備或稽核紀錄，此測試應失敗。"""
    batch = _preview()
    first = MsaImportService.confirm(
        batch.id,
        actor_id=1,
        resolutions={},
        confirmation_date=date(2026, 7, 27),
    )
    second = MsaImportService.confirm(
        batch.id,
        actor_id=1,
        resolutions={},
        confirmation_date=date(2026, 7, 27),
    )

    assert second.id == first.id
    assert MeasurementEquipment.query.count() == first.success_rows
    assert (
        AuditLog.query.filter_by(
            module="msa_equipment_import",
            action="confirm",
            record_id=batch.id,
        ).count()
        == 1
    )


def test_confirm_rejects_invalid_resolution_without_state_change(db_session):
    """無效 resolution 若被接受或把 batch 錯標 confirmed，此測試應失敗。"""
    batch = _preview()
    ambiguous = next(
        row
        for row in EquipmentImportRow.query.filter_by(batch_id=batch.id)
        if row.normalized_data["equipment_no"] == "EQ-TEST-005"
    )

    with pytest.raises(MsaValidationError) as error:
        MsaImportService.confirm(
            batch.id,
            actor_id=1,
            resolutions={
                str(ambiguous.id): {
                    "action": "accept",
                    "calibration_type": "guess",
                }
            },
            confirmation_date=date(2026, 7, 27),
        )

    assert error.value.code == "MSA_IMPORT_RESOLUTION_INVALID"
    db_session.expire_all()
    assert db_session.get(EquipmentImportBatch, batch.id).status == "previewed"
    assert MeasurementEquipment.query.count() == 0


def test_confirm_rolls_back_whole_batch_on_duplicate_equipment(db_session):
    """後列衝突時若留下前列設備、稽核或 confirmed 狀態，此測試應失敗。"""
    batch = _preview()
    db_session.add(
        MeasurementEquipment(
            equipment_no="EQ-TEST-002",
            name="既有設備",
            status="pending_review",
        )
    )
    db_session.commit()

    with pytest.raises(MsaConflict) as error:
        MsaImportService.confirm(
            batch.id,
            actor_id=1,
            resolutions={},
            confirmation_date=date(2026, 7, 27),
        )

    assert error.value.code == "MSA_IMPORT_EQUIPMENT_NO_DUPLICATE"
    db_session.expire_all()
    assert db_session.get(EquipmentImportBatch, batch.id).status == "previewed"
    assert [
        item.equipment_no
        for item in MeasurementEquipment.query.order_by(
            MeasurementEquipment.equipment_no
        )
    ] == ["EQ-TEST-002"]
    assert (
        AuditLog.query.filter_by(module="msa_equipment_import").count() == 0
    )

"""更新溫度記錄器模板 V1：不重複測量、以當前讀值判定。"""

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from ..app import app
from ..extensions import db
from ..models import CalibrationTemplate, CalibrationTemplateVersion
from ..services.calibration_template_service import CalibrationTemplateService

CHANNELS = [f"CH{i}" for i in range(1, 19)]
TEMPERATURES = [100, 200, 300, 400, 500, 600]

points = []
point_order = 1
for ch in CHANNELS:
    for temp in TEMPERATURES:
        points.append(
            {
                "point_order": point_order,
                "point_code": f"{ch}-T{temp}",
                "measurement_mode": "溫度校正",
                "nominal_value": str(temp),
                "unit": "℃",
                "reference_input_mode": "certified_value",
                "required_repetitions": 1,
                "error_lower_limit": "-1",
                "error_upper_limit": "1",
                "evaluation_basis": "all_readings",
                "repeatability_rule": "none",
                "repeatability_limit": None,
                "qualification_scope_code": "TEMP-REC",
                "qualification_range_start": "100",
                "qualification_range_end": "600",
                "uncertainty_required": False,
                "required": True,
                "instruction": f"將標準溫度源設定為 {temp}℃，待穩定後記錄 {ch} 通道當前讀值",
            }
        )
        point_order += 1


def main():
    with app.app_context():
        t = (
            db.session.query(CalibrationTemplate)
            .filter_by(template_code="CAL-溫度記錄器-001")
            .first()
        )
        v = (
            db.session.query(CalibrationTemplateVersion)
            .filter_by(template_id=t.id)
            .order_by(CalibrationTemplateVersion.version_no.desc())
            .first()
        )

        result = CalibrationTemplateService.update_version(
            v.id,
            {
                "expected_version": v.row_version,
                "points": points,
            },
            actor_id=1,
        )

        first = result["points"][0]
        print(f"✅ V{v.version_no} 更新完成")
        print(f"  狀態：{result['status']}")
        print(f"  row_version：{result['row_version']}")
        print(f"  校正點：{len(result['points'])} 個")
        print(f"  重複次數：{first['required_repetitions']}")
        print(f"  判定基礎：{first['evaluation_basis']}")
        print(f"  操作指示：{first['instruction']}")


if __name__ == "__main__":
    main()

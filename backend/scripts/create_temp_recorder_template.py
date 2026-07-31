"""批次建立溫度記錄器校正模板（18通道 × 6溫度 = 108 校正點）

用法（repo 根目錄）：
    python -m backend.scripts.create_temp_recorder_template
"""

import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from ..app import app
from ..extensions import db
from ..models import CalibrationTemplate, User
from ..services.calibration_template_service import CalibrationTemplateService

TEMPLATE_CODE = "CAL-溫度記錄器-001"
TEMPLATE_NAME = "TAF溫度記錄器校正"
EQUIPMENT_TYPE = "溫度記錄器"

# 18 通道 × 6 溫度
CHANNELS = [f"CH{i}" for i in range(1, 19)]
TEMPERATURES = [100, 200, 300, 400, 500, 600]

# 公差規格：±1℃
ERROR_LOWER = "-1"
ERROR_UPPER = "1"

VERSION_PAYLOAD = {
    "procedure_code": "WI-TEMP-001",
    "procedure_name": "溫度記錄器校正作業程序",
    "procedure_description": "TAF 溫度記錄器校正，使用標準熱電偶溫度源進行各通道比對",
    "default_repetitions": 3,
    "environment_requirements": {
        "temperature": {"unit": "℃", "minimum": "15", "maximum": "35", "required": False},
        "humidity": {"unit": "%RH", "minimum": "20", "maximum": "80", "required": False},
    },
    "allow_limited_use": False,
    "revision_reason": "初始版本",
    "points": [],
}

# 建立 108 個校正點
point_order = 1
for ch in CHANNELS:
    for temp in TEMPERATURES:
        VERSION_PAYLOAD["points"].append({
            "point_order": point_order,
            "point_code": f"{ch}-T{temp}",
            "measurement_mode": "溫度校正",
            "nominal_value": str(temp),
            "unit": "℃",
            "reference_input_mode": "certified_value",
            "required_repetitions": 3,
            "error_lower_limit": ERROR_LOWER,
            "error_upper_limit": ERROR_UPPER,
            "evaluation_basis": "mean_error",
            "repeatability_rule": "none",
            "repeatability_limit": None,
            "qualification_scope_code": "TEMP-REC",
            "qualification_range_start": "100",
            "qualification_range_end": "600",
            "uncertainty_required": False,
            "required": True,
            "instruction": f"將標準溫度源設定為 {temp}℃，記錄 {ch} 通道 3 次讀值後取平均誤差判定",
        })
        point_order += 1


def main():
    with app.app_context():
        # 找第一個啟用使用者作為 actor（通常是 admin）
        actor = db.session.query(User).filter_by(is_active=True).order_by(User.id).first()
        if actor is None:
            print("錯誤：找不到任何啟用中的使用者")
            sys.exit(1)
        print(f"使用使用者：{actor.username} (id={actor.id})")

        # 1. 檢查模板是否已存在
        existing = db.session.query(CalibrationTemplate).filter_by(
            template_code=TEMPLATE_CODE
        ).first()
        if existing:
            template_id = existing.id
            print(f"模板「{TEMPLATE_CODE}」已存在：id={template_id}，跳過建立")
        else:
            print(f"正在建立模板「{TEMPLATE_CODE}」…")
            template = CalibrationTemplateService.create(
                {
                    "template_code": TEMPLATE_CODE,
                    "name": TEMPLATE_NAME,
                    "equipment_type": EQUIPMENT_TYPE,
                    "description": "18 通道溫度記錄器校正模板，涵蓋 100~600℃ 共 6 個標準溫度點，誤差界限 ±1℃",
                },
                actor_id=actor.id,
            )
            template_id = template["id"]
            print(f"模板建立完成：id={template_id}")

        # 2. 建立版本（含 108 校正點）
        print(f"正在建立版本（含 {len(VERSION_PAYLOAD['points'])} 個校正點）…")
        version = CalibrationTemplateService.create_version(
            template_id,
            VERSION_PAYLOAD,
            actor_id=actor.id,
        )
        print(f"版本建立完成：version_no={version['version_no']}, id={version['id']}")
        print(f"校正點數量：{len(version['points'])}")

        # 3. 自動送審+核准（若需要可直接使用）
        print("\n✅ 模板建立成功！")
        print(f"   模板 ID：{template_id}")
        print(f"   模板代碼：{TEMPLATE_CODE}")
        print(f"   版本：V{version['version_no']} (id={version['id']})")
        print(f"   狀態：{version['status']}")
        print("\n後續步驟：")
        print(f"   1. 前往 http://localhost:5173/calibration/templates/{template_id} 檢視")
        print("   2. 將版本「送審」→「核准」後即可用於建立校正記錄")


if __name__ == "__main__":
    main()

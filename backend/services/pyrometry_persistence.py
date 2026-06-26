from typing import Any

from .pyrometry_calculations import to_float


def parse_optional_channel(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def build_point_model_kwargs(test_type: str, test_id: int, point: dict[str, Any]) -> dict[str, Any]:
    if test_type == "TUS":
        return {
            "test_id": test_id,
            "position": point.get("點位"),
            "tc_no": point.get("熱電偶編號"),
            "channel": parse_optional_channel(point.get("頻道")),
            "correction": to_float(point.get("修正值")),
            "temp_max": to_float(point.get("最高溫")),
            "temp_min": to_float(point.get("最低溫")),
            "max_dev": to_float(point.get("最大偏差")),
            "is_pass": point.get("是否合格", True),
        }

    return {
        "test_id": test_id,
        "zone": point.get("控溫區"),
        "channel": parse_optional_channel(point.get("頻道")),
        "readings": point.get("readings") or None,
        "diff": to_float(point.get("差值")),
        "correction": to_float(point.get("修正值")),
        "deviation": to_float(point.get("偏差")),
        "is_pass": point.get("是否合格", True),
    }

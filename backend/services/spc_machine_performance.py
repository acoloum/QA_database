"""巡檢固定機台研究的 Pm／Pmk G 法指數。"""

from math import isfinite
from typing import Any, Mapping, Sequence

from .spc_distribution import dist_quantiles


MACHINE_TARGETS = {
    "關鍵": {"pm": 2.33, "pmk": 2.00},
    "主要": {"pm": 2.00, "pmk": 1.67},
    "次要": {"pm": 1.67, "pmk": 1.33},
    "其他": {"pm": 1.00, "pmk": 1.00},
}
MACHINE_MINIMUM_SAMPLE = 50


def _targets(characteristic_class: str | None) -> dict[str, Any]:
    selected = characteristic_class if characteristic_class in MACHINE_TARGETS else "其他"
    return {"class": selected, **MACHINE_TARGETS[selected]}


def _result(
    *, values: Sequence[float], characteristic_class: str | None,
    available: bool, reason_code: str | None, distribution: Mapping[str, Any],
    q_lo: float | None = None, q_mid: float | None = None, q_hi: float | None = None,
    pm: float | None = None, pmu: float | None = None, pml: float | None = None,
    specification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    count = len(values)
    preliminary = count < MACHINE_MINIMUM_SAMPLE
    return {
        "available": available,
        "index_family": "machine",
        "method": "G",
        "n": count,
        "preliminary": preliminary,
        "reason_code": reason_code,
        "distribution": {
            "model": distribution.get("model"),
            "label": distribution.get("label"),
            "accepted": bool(distribution.get("accepted")),
            "reason_code": distribution.get("reason_code"),
        },
        "quantiles": {"q_0_135": q_lo, "q_50": q_mid, "q_99_865": q_hi},
        "usl": (specification or {}).get("USL"),
        "lsl": (specification or {}).get("LSL"),
        "pm": pm,
        "pmu": pmu,
        "pml": pml,
        "pmk": min(value for value in (pmu, pml) if value is not None)
        if pmu is not None or pml is not None else None,
        "targets": _targets(characteristic_class),
        "approvable": bool(available and not preliminary),
    }


def calculate_machine_performance(
    values: Sequence[float], specification: Mapping[str, Any],
    distribution: Mapping[str, Any], characteristic_class: str | None,
) -> dict[str, Any]:
    """以 G 法分位數計算固定機台 Pm／Pmk，不回退至未確認分布。"""

    numeric = [float(value) for value in values]
    if not numeric or not all(isfinite(value) for value in numeric):
        return _result(
            values=numeric, characteristic_class=characteristic_class, available=False,
            reason_code="MACHINE_SAMPLE_INSUFFICIENT", distribution=distribution,
            specification=specification,
        )
    if len(numeric) < MACHINE_MINIMUM_SAMPLE:
        return _result(
            values=numeric, characteristic_class=characteristic_class, available=False,
            reason_code="MACHINE_SAMPLE_INSUFFICIENT", distribution=distribution,
            specification=specification,
        )
    if not distribution.get("accepted"):
        return _result(
            values=numeric, characteristic_class=characteristic_class, available=False,
            reason_code=distribution.get("reason_code") or "DISTRIBUTION_UNCONFIRMED",
            distribution=distribution, specification=specification,
        )
    if not specification.get("found") or specification.get("consistent") is False:
        return _result(
            values=numeric, characteristic_class=characteristic_class, available=False,
            reason_code=specification.get("reason_code") or "SPECIFICATION_UNCONFIRMED",
            distribution=distribution,
            specification=specification,
        )

    lsl = specification.get("LSL")
    usl = specification.get("USL")
    if lsl is None and usl is None:
        return _result(
            values=numeric, characteristic_class=characteristic_class, available=False,
            reason_code="SPECIFICATION_UNCONFIRMED", distribution=distribution,
            specification=specification,
        )
    q_lo, q_mid, q_hi = dist_quantiles(dict(distribution))
    if None in (q_lo, q_mid, q_hi) or q_hi <= q_lo:
        return _result(
            values=numeric, characteristic_class=characteristic_class, available=False,
            reason_code="DISTRIBUTION_UNCONFIRMED", distribution=distribution,
            specification=specification,
        )
    pm = (float(usl) - float(lsl)) / (q_hi - q_lo) if usl is not None and lsl is not None else None
    pmu = (float(usl) - q_mid) / (q_hi - q_mid) if usl is not None and q_hi > q_mid else None
    pml = (q_mid - float(lsl)) / (q_mid - q_lo) if lsl is not None and q_mid > q_lo else None
    return _result(
        values=numeric, characteristic_class=characteristic_class, available=True,
        reason_code=None, distribution=distribution, q_lo=q_lo, q_mid=q_mid, q_hi=q_hi,
        pm=pm, pmu=pmu, pml=pml, specification=specification,
    )

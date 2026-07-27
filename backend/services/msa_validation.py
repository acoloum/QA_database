"""統計引擎的 golden validation runner。

PASS 與 FAIL 都必須留下不可變的執行紀錄——確效的價值正在於失敗
也留痕，因此比對失敗不是例外，而是一筆據實記錄的 FAIL。
"""

import hashlib
import json
import math
from pathlib import Path

from ..extensions import db
from ..models import MsaValidationRun
from .msa_analysis_service import CODE_VERSION
from .msa_contracts import MsaMethodContext
from .msa_errors import MsaMethodNotApplicable, MsaNotFound
from .msa_method_registry import MsaMethodRegistry


GOLDEN_CASES_PATH = (
    Path(__file__).resolve().parents[1]
    / "tests" / "fixtures" / "msa_golden_cases.json"
)

DEFAULT_TOLERANCE = 1e-9


class MsaValidationService:
    """執行受控 golden case 並持久化比對結果。"""

    @staticmethod
    def load_cases(path: Path | None = None) -> dict:
        source = Path(path or GOLDEN_CASES_PATH)
        payload = json.loads(source.read_text(encoding="utf-8"))
        return payload["cases"]

    @staticmethod
    def fixture_hash(path: Path | None = None) -> str:
        source = Path(path or GOLDEN_CASES_PATH)
        return hashlib.sha256(source.read_bytes()).hexdigest()

    @staticmethod
    def case_codes(path: Path | None = None) -> tuple[str, ...]:
        return tuple(sorted(MsaValidationService.load_cases(path)))

    @staticmethod
    def run_case(
        case_code: str, *, actor_id: int | None = None, path: Path | None = None,
    ) -> MsaValidationRun:
        cases = MsaValidationService.load_cases(path)
        case = cases.get(case_code)
        if case is None:
            raise MsaNotFound(
                "MSA_VALIDATION_CASE_NOT_FOUND",
                "找不到 golden validation 案例",
                details={"case_code": case_code, "available": sorted(cases)},
            )

        descriptor = MsaMethodRegistry.get(case["method_code"])
        context = MsaMethodContext(**case["context"])
        expected = case.get("expected") or {}
        tolerances = case.get("tolerances") or {}
        expected_not_applicable = case.get("expect_not_applicable")

        observed = {}
        differences = []
        try:
            output = descriptor.engine(case["input"], context)
            if expected_not_applicable:
                differences.append(
                    f"預期判定為不適用（{expected_not_applicable}），"
                    "但引擎產生了結果"
                )
                observed = {"not_applicable": False}
            else:
                observed = MsaValidationService._collect(output, expected)
                differences = MsaValidationService._compare(
                    observed, expected, tolerances,
                )
        except MsaMethodNotApplicable as error:
            observed = {
                "not_applicable": True, "reason": error.details.get("reason"),
            }
            if not expected_not_applicable:
                differences.append(
                    f"預期產生結果，但引擎判定不適用（{observed['reason']}）"
                )
            elif observed["reason"] != expected_not_applicable:
                differences.append(
                    f"不適用理由不符：預期 {expected_not_applicable}，"
                    f"實得 {observed['reason']}"
                )

        if not CODE_VERSION:
            differences.append("缺少統計引擎程式版本，無法建立可追溯的確效")

        run = MsaValidationRun(
            case_code=case_code,
            fixture_hash=MsaValidationService.fixture_hash(path),
            method_versions={descriptor.code: descriptor.version},
            code_version=CODE_VERSION,
            tolerances=tolerances,
            observed=_jsonable(observed),
            expected=_jsonable(
                expected if not expected_not_applicable
                else {"not_applicable": True,
                      "reason": expected_not_applicable}
            ),
            differences=differences,
            result="PASS" if not differences else "FAIL",
            executed_by_id=actor_id,
        )
        db.session.add(run)
        db.session.commit()
        return run

    @staticmethod
    def run_all(
        *, actor_id: int | None = None, path: Path | None = None,
    ) -> list:
        return [
            MsaValidationService.run_case(
                case_code, actor_id=actor_id, path=path,
            )
            for case_code in MsaValidationService.case_codes(path)
        ]

    # ------------------------------------------------------------------
    # 比對
    # ------------------------------------------------------------------

    @staticmethod
    def _collect(output, expected: dict) -> dict:
        """依期望值的路徑取出實際值，避免把整棵樹塞進紀錄。"""
        tree = {
            "statistics": output.statistics,
            "applicability": output.applicability,
            "chart_data": output.chart_data,
        }
        return {path: _dig(tree, path) for path in expected}

    @staticmethod
    def _compare(observed: dict, expected: dict, tolerances: dict) -> list:
        differences = []
        for path, wanted in expected.items():
            actual = observed.get(path)
            tolerance = tolerances.get(path, DEFAULT_TOLERANCE)
            if isinstance(wanted, bool) or wanted is None:
                if actual != wanted:
                    differences.append(
                        f"{path}：預期 {wanted}，實得 {actual}"
                    )
                continue
            if isinstance(wanted, (int, float)) and isinstance(
                actual, (int, float)
            ) and not isinstance(actual, bool):
                if not math.isfinite(actual):
                    differences.append(f"{path}：實得非有限值 {actual}")
                elif abs(actual - wanted) > abs(tolerance * max(1.0, abs(wanted))):
                    differences.append(
                        f"{path}：預期 {wanted}，實得 {actual}"
                        f"（容許誤差 {tolerance}）"
                    )
                continue
            if actual != wanted:
                differences.append(f"{path}：預期 {wanted}，實得 {actual}")
        return differences


_MISSING = object()


def _dig(tree, path: str):
    """以點號路徑取值；陣列索引以數字表示。"""
    current = tree
    for token in path.split("."):
        if isinstance(current, dict):
            current = current.get(token, _MISSING)
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(token)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if current is _MISSING:
            return None
    return current


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value

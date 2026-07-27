"""執行 MSA 統計引擎的 golden validation 並持久化結果。

PASS 與 FAIL 都會留下不可變紀錄；有任何 FAIL 時以非零 exit code 結束。

用法：
    venv\\Scripts\\python.exe -m backend.scripts.run_msa_validation
    venv\\Scripts\\python.exe -m backend.scripts.run_msa_validation \\
        --case grr_xbar_r_reference
"""

import argparse
import json

from ..app import app
from ..services.msa_validation import MsaValidationService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="執行 MSA 統計引擎 golden validation",
    )
    parser.add_argument(
        "--case", action="append", default=None,
        help="只執行指定案例；可重複指定，未指定時執行全部",
    )
    parser.add_argument(
        "--actor-id", type=int, default=None,
        help="執行者使用者 ID",
    )
    args = parser.parse_args()

    with app.app_context():
        case_codes = args.case or list(MsaValidationService.case_codes())
        runs = [
            MsaValidationService.run_case(code, actor_id=args.actor_id)
            for code in case_codes
        ]
        failures = [run for run in runs if run.result == "FAIL"]
        print(json.dumps(
            {
                "fixture_hash": MsaValidationService.fixture_hash(),
                "code_version": runs[0].code_version if runs else None,
                "total": len(runs),
                "passed": len(runs) - len(failures),
                "failed": len(failures),
                "run_ids": [run.id for run in runs],
                "results": [
                    {
                        "id": run.id,
                        "case_code": run.case_code,
                        "result": run.result,
                        "differences": run.differences,
                    }
                    for run in runs
                ],
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

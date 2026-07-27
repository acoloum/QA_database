"""為已到期的核准研究建立週期再研究要求。

可安全重複執行：同一研究的同一到期日只會產生一筆要求。

用法：
    venv\\Scripts\\python.exe -m backend.scripts.create_due_msa_restudies \\
        --as-of 2026-07-27
"""

import argparse
import json
from datetime import date

from ..app import app
from ..services.msa_restudy_service import MsaRestudyService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="建立到期的 MSA 週期再研究要求（冪等）",
    )
    parser.add_argument(
        "--as-of",
        default=date.today().isoformat(),
        help="判定到期的基準日（ISO 日期，預設今天）",
    )
    parser.add_argument(
        "--actor-id", type=int, default=None,
        help="建立者使用者 ID；未指定時不記錄建立者",
    )
    args = parser.parse_args()

    try:
        as_of = date.fromisoformat(args.as_of)
    except ValueError:
        parser.error("--as-of 必須是 ISO 日期，例如 2026-07-27")
        return 2

    with app.app_context():
        created = MsaRestudyService.create_periodic_due(
            as_of, actor_id=args.actor_id,
        )
        print(json.dumps(
            {
                "as_of": as_of.isoformat(),
                "open_requests": len(created),
                "requests": [
                    {
                        "id": item.id,
                        "source_study_id": item.source_study_id,
                        "due_date": (
                            item.due_date.isoformat() if item.due_date else None
                        ),
                        "status": item.status,
                    }
                    for item in created
                ],
            },
            ensure_ascii=False,
            indent=2,
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

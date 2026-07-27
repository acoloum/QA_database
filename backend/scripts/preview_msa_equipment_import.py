"""唯讀盤點設備 CSV，不建立匯入批次或正式設備。"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from backend.services.msa_import_service import (
    _read_bounded_source,
    inspect_equipment_csv,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="唯讀預覽 MSA 設備清單 CSV 的正規化統計"
    )
    parser.add_argument("csv_path", type=Path, help="設備清單 CSV 路徑")
    parser.add_argument(
        "--as-of",
        required=True,
        type=date.fromisoformat,
        help="重新計算逾期的基準日，格式 YYYY-MM-DD",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    content, file_sha256 = _read_bounded_source(args.csv_path)
    inspection = inspect_equipment_csv(content, as_of=args.as_of)
    output = {
        "mode": "read_only",
        "as_of": args.as_of.isoformat(),
        "file_sha256": file_sha256,
        "encoding": inspection.encoding,
        **inspection.statistics,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

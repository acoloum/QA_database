# -*- coding: utf-8 -*-
"""清除所有 smoke 測試資料（動態掃描 SMOKE- 前綴，不硬編碼 ID）。

供 smoke 重跑前清理歷史殘留，或手動清除不再需要的 smoke 資料。

特色：
- 動態收集：以「設備編號/模板代碼/程序代碼/準則名稱/品質特性 LIKE 'SMOKE-%'」
  為根，向下依 FK 關聯收集全部子資料（校驗紀錄、附件、MSA 計畫/零件/評價人/
  觀測/結果/決策等），不需維護 ID 清單。
- 不可變證據保護：核准/凍結資料受 immutable 觸發器保護，superuser 才能刪除。
  腳本會動態停用目標表觸發器 → 刪除 → 無論成敗恢復，並驗證無殘留停用。
- 附件實體檔：commit 成功後以 STORAGE 後端刪除實體檔。
- 稽核日誌（操作日誌）只回報，不刪除。
- 孤兒檢查：任何「非 smoke 資料引用將刪除之 smoke 資料」都會阻擋並 rollback。

用法（repo 根目錄）：
    .\\venv\\Scripts\\python.exe -m backend.scripts.cleanup_smoke_data            # dry-run，只統計
    .\\venv\\Scripts\\python.exe -m backend.scripts.cleanup_smoke_data --apply    # 實際清除
"""

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from sqlalchemy import text  # noqa: E402

from ..app import app  # noqa: E402
from ..extensions import db  # noqa: E402

MSG_LINE = "=" * 68

# 將刪除資料的所有表（含可能 0 筆但受觸發器保護者）
TARGET_TABLES = (
    "MSA觀測", "MSA觀測匯入批次", "MSA結果版本", "MSA工作流決策",
    "MSA再研究要求", "MSA零件", "MSA評價人", "MSA研究設備",
    "MSA計畫版本", "MSA研究", "MSA準則版本", "MSA準則設定",
    "設備校正原始讀值", "設備校正點", "校正參考標準器快照",
    "設備校驗補正點", "附件", "設備校驗紀錄",
    "校正模板校正點", "校正模板版本", "校正模板",
    "設備狀態事件", "量測設備連結", "設備匯入列", "量測設備",
)

# 收集根 ID 的前綴條件（同時涵蓋 smoke_calibration 的 SMOKE-CAL-* 與 smoke_msa 的 SMOKE-MSA-*）
SMOKE_LIKE = "SMOKE-%"


def _q1(sql, **params):
    """回傳單一純量值。"""
    return db.session.execute(text(sql), params).scalar()


def _rows(sql, **params):
    """回傳 (id,) 行清單。"""
    return db.session.execute(text(sql), params).fetchall()


def _collect_ids(sql, **params) -> tuple[int, ...]:
    """收集單欄 ID tuple；空集合時回傳空 tuple。"""
    return tuple(row[0] for row in _rows(sql, **params))


def _collect_triggers() -> list[tuple[str, str, str]]:
    """回傳 [(表名, 觸發器名, 原tgenabled)]，僅限啟用中的非內部觸發器。"""
    rows = db.session.execute(
        text(
            """
            SELECT c.relname, t.tgname, t.tgenabled
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname IN :tables
              AND t.tgname IS NOT NULL
              AND NOT t.tgisinternal
              AND t.tgenabled <> 'D'
            ORDER BY c.relname, t.tgname
            """
        ),
        {"tables": TARGET_TABLES},
    ).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def _set_triggers(triggers: list[tuple[str, str, str]], enable: bool) -> None:
    """以 AUTOCOMMIT 連線停用或恢復觸發器。enable=True 時依原 tgenabled 恢復。"""
    with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for table, tname, original in triggers:
            if enable:
                if original == "R":
                    stmt = f'ALTER TABLE "{table}" ENABLE REPLICA TRIGGER "{tname}"'
                elif original == "A":
                    stmt = f'ALTER TABLE "{table}" ENABLE ALWAYS TRIGGER "{tname}"'
                else:
                    stmt = f'ALTER TABLE "{table}" ENABLE TRIGGER "{tname}"'
            else:
                stmt = f'ALTER TABLE "{table}" DISABLE TRIGGER "{tname}"'
            conn.execute(text(stmt))


def _collect_scope() -> dict[str, tuple[int, ...]]:
    """動態收集全部 smoke 資料的 ID 集合（以 FK 關聯向下展開）。"""
    scope: dict[str, tuple[int, ...]] = {}

    # 根實體（SMOKE- 前綴）
    scope["eq_ids"] = _collect_ids(
        'SELECT "識別碼" FROM "量測設備" WHERE "設備編號" LIKE :p', p=SMOKE_LIKE
    )
    scope["tpl_ids"] = _collect_ids(
        'SELECT "識別碼" FROM "校正模板" WHERE "模板代碼" LIKE :p', p=SMOKE_LIKE
    )

    # 模板版本：模板ID 屬 smoke 或程序代碼帶 SMOKE- 前綴
    scope["ver_ids"] = _collect_ids(
        """
        SELECT "識別碼" FROM "校正模板版本"
        WHERE "模板ID" IN :tpl_ids OR "程序代碼" LIKE :p
        """,
        tpl_ids=scope["tpl_ids"] or (0,),
        p=SMOKE_LIKE,
    )
    # 模板校正點
    scope["tpl_point_ids"] = _collect_ids(
        'SELECT "識別碼" FROM "校正模板校正點" WHERE "模板版本ID" IN :ids',
        ids=scope["ver_ids"] or (0,),
    )

    # 校驗紀錄：設備屬 smoke 或模板版本屬 smoke
    scope["rec_ids"] = _collect_ids(
        """
        SELECT "識別碼" FROM "設備校驗紀錄"
        WHERE "設備ID" IN :eq_ids OR "模板版本ID" IN :ver_ids
        """,
        eq_ids=scope["eq_ids"] or (0,),
        ver_ids=scope["ver_ids"] or (0,),
    )
    # 校正點與讀值
    scope["point_ids"] = _collect_ids(
        'SELECT "識別碼" FROM "設備校正點" WHERE "校驗紀錄ID" IN :ids',
        ids=scope["rec_ids"] or (0,),
    )
    # 參考快照（含核准快照指向）
    scope["snap_ids"] = _collect_ids(
        """
        SELECT "識別碼" FROM "校正參考標準器快照"
        WHERE "校驗紀錄ID" IN :ids OR "核准校驗紀錄ID" IN :ids
        """,
        ids=scope["rec_ids"] or (0,),
    )
    # 設備校驗補正點（若表存在）
    scope["corr_ids"] = ()
    if _q1('SELECT to_regclass(:t)', t='"設備校驗補正點"'):
        scope["corr_ids"] = _collect_ids(
            'SELECT "識別碼" FROM "設備校驗補正點" WHERE "校驗紀錄ID" IN :ids',
            ids=scope["rec_ids"] or (0,),
        )
    # 附件（校驗紀錄或設備的附件）
    scope["att_ids"] = _collect_ids(
        """
        SELECT "識別碼" FROM "附件"
        WHERE ("實體類型" = 'equipment_calibration' AND "實體ID" IN :rec_ids)
           OR ("實體類型" = 'measurement_equipment' AND "實體ID" IN :eq_ids)
        """,
        rec_ids=scope["rec_ids"] or (0,),
        eq_ids=scope["eq_ids"] or (0,),
    )

    # MSA 準則
    scope["criteria_ids"] = _collect_ids(
        'SELECT "識別碼" FROM "MSA準則設定" WHERE "名稱" LIKE :p', p=SMOKE_LIKE
    )
    scope["criteria_ver_ids"] = _collect_ids(
        'SELECT "識別碼" FROM "MSA準則版本" WHERE "準則設定ID" IN :ids',
        ids=scope["criteria_ids"] or (0,),
    )
    # MSA 研究（品質特性帶 SMOKE- 前綴）
    scope["study_ids"] = _collect_ids(
        """
        SELECT "識別碼" FROM "MSA研究"
        WHERE "品質特性" LIKE :p OR "研究編號" LIKE :p2
        """,
        p=SMOKE_LIKE,
        p2=SMOKE_LIKE,
    )
    # MSA 計畫版本與其子表
    scope["plan_ids"] = _collect_ids(
        'SELECT "識別碼" FROM "MSA計畫版本" WHERE "研究ID" IN :ids',
        ids=scope["study_ids"] or (0,),
    )
    scope["part_ids"] = _collect_ids(
        'SELECT "識別碼" FROM "MSA零件" WHERE "計畫版本ID" IN :ids',
        ids=scope["plan_ids"] or (0,),
    )
    scope["appr_ids"] = _collect_ids(
        'SELECT "識別碼" FROM "MSA評價人" WHERE "計畫版本ID" IN :ids',
        ids=scope["plan_ids"] or (0,),
    )
    scope["obs_ids"] = _collect_ids(
        'SELECT "識別碼" FROM "MSA觀測" WHERE "計畫版本ID" IN :ids',
        ids=scope["plan_ids"] or (0,),
    )
    scope["batch_ids"] = _collect_ids(
        'SELECT "識別碼" FROM "MSA觀測匯入批次" WHERE "計畫版本ID" IN :ids',
        ids=scope["plan_ids"] or (0,),
    )
    scope["result_ids"] = _collect_ids(
        """
        SELECT "識別碼" FROM "MSA結果版本"
        WHERE "研究ID" IN :study_ids OR "計畫版本ID" IN :plan_ids
        """,
        study_ids=scope["study_ids"] or (0,),
        plan_ids=scope["plan_ids"] or (0,),
    )
    scope["decision_ids"] = _collect_ids(
        'SELECT "識別碼" FROM "MSA工作流決策" WHERE "研究ID" IN :ids',
        ids=scope["study_ids"] or (0,),
    )
    scope["restudy_ids"] = _collect_ids(
        """
        SELECT "識別碼" FROM "MSA再研究要求"
        WHERE "來源研究ID" IN :ids OR "新研究ID" IN :ids
        """,
        ids=scope["study_ids"] or (0,),
    )
    scope["study_equip_ids"] = _collect_ids(
        'SELECT "識別碼" FROM "MSA研究設備" WHERE "研究ID" IN :ids',
        ids=scope["study_ids"] or (0,),
    )
    # 設備周邊
    scope["status_event_ids"] = _collect_ids(
        'SELECT "識別碼" FROM "設備狀態事件" WHERE "設備ID" IN :ids',
        ids=scope["eq_ids"] or (0,),
    )
    scope["link_ids"] = _collect_ids(
        'SELECT "識別碼" FROM "量測設備連結" WHERE "設備ID" IN :ids',
        ids=scope["eq_ids"] or (0,),
    )
    scope["import_row_ids"] = _collect_ids(
        'SELECT "識別碼" FROM "設備匯入列" WHERE "對應設備ID" IN :ids',
        ids=scope["eq_ids"] or (0,),
    )
    return scope


def _run_checks(scope: dict[str, tuple[int, ...]], lines: list[str]) -> None:
    """前檢核：數量對照 + 孤兒檢查（非 smoke 資料引用將刪除資料 → 阻擋）。"""
    lines.append(MSG_LINE)
    lines.append("前檢核")
    lines.append(MSG_LINE)

    expect = [
        ("量測設備", scope["eq_ids"]),
        ("校正模板", scope["tpl_ids"]),
        ("校正模板版本", scope["ver_ids"]),
        ("校正模板校正點", scope["tpl_point_ids"]),
        ("設備校驗紀錄", scope["rec_ids"]),
        ("設備校正點", scope["point_ids"]),
        ("校正參考標準器快照", scope["snap_ids"]),
        ("附件", scope["att_ids"]),
        ("MSA準則設定", scope["criteria_ids"]),
        ("MSA準則版本", scope["criteria_ver_ids"]),
        ("MSA研究", scope["study_ids"]),
        ("MSA計畫版本", scope["plan_ids"]),
        ("MSA零件", scope["part_ids"]),
        ("MSA評價人", scope["appr_ids"]),
        ("MSA觀測", scope["obs_ids"]),
        ("MSA結果版本", scope["result_ids"]),
        ("MSA工作流決策", scope["decision_ids"]),
    ]
    for name, ids in expect:
        lines.append(f"  [{len(ids)} 筆] {name}")
    if scope["corr_ids"]:
        lines.append(f"  [{len(scope['corr_ids'])} 筆] 設備校驗補正點")

    orphan_checks = [
        ("其他 校驗紀錄 引用 smoke 模板版本",
         'SELECT count(*) FROM "設備校驗紀錄" WHERE "模板版本ID" IN :ids AND "設備ID" NOT IN :eq_ids',
         dict(ids=scope["ver_ids"] or (0,), eq_ids=scope["eq_ids"] or (0,))),
        ("其他 校驗紀錄.參考標準設備 指向 smoke 設備",
         'SELECT count(*) FROM "設備校驗紀錄" WHERE "參考標準設備ID" IN :ids AND "設備ID" NOT IN :eq_ids',
         dict(ids=scope["eq_ids"] or (0,), eq_ids=scope["eq_ids"] or (0,))),
        ("其他 校正點 引用 smoke 模板校正點",
         'SELECT count(*) FROM "設備校正點" WHERE "模板校正點ID" IN :ids AND "校驗紀錄ID" NOT IN :rec_ids',
         dict(ids=scope["tpl_point_ids"] or (0,), rec_ids=scope["rec_ids"] or (0,))),
        ("其他 校驗紀錄 引用 smoke 附件",
         'SELECT count(*) FROM "設備校驗紀錄" WHERE "原始證書附件ID" IN :ids AND "識別碼" NOT IN :rec_ids',
         dict(ids=scope["att_ids"] or (0,), rec_ids=scope["rec_ids"] or (0,))),
        ("其他 參考快照.參考標準設備 指向 smoke 設備",
         'SELECT count(*) FROM "校正參考標準器快照" WHERE "參考標準設備ID" IN :ids AND "識別碼" NOT IN :snap_ids',
         dict(ids=scope["eq_ids"] or (0,), snap_ids=scope["snap_ids"] or (0,))),
        ("其他 MSA研究 引用 smoke 準則設定",
         'SELECT count(*) FROM "MSA研究" WHERE "準則設定ID" IN :ids AND "識別碼" NOT IN :study_ids',
         dict(ids=scope["criteria_ids"] or (0,), study_ids=scope["study_ids"] or (0,))),
        ("其他 MSA研究.前次核准研究ID 指向 smoke 研究",
         'SELECT count(*) FROM "MSA研究" WHERE "前次核准研究ID" IN :ids AND "識別碼" NOT IN :study_ids',
         dict(ids=scope["study_ids"] or (0,), study_ids=scope["study_ids"] or (0,))),
        ("其他 MSA結果版本 引用 smoke 研究/計畫",
         'SELECT count(*) FROM "MSA結果版本" WHERE ("研究ID" IN :study_ids OR "計畫版本ID" IN :plan_ids) AND "識別碼" NOT IN :result_ids',
         dict(study_ids=scope["study_ids"] or (0,), plan_ids=scope["plan_ids"] or (0,), result_ids=scope["result_ids"] or (0,))),
        ("其他 MSA觀測 引用 smoke 計畫",
         'SELECT count(*) FROM "MSA觀測" WHERE "計畫版本ID" IN :ids AND "識別碼" NOT IN :obs_ids',
         dict(ids=scope["plan_ids"] or (0,), obs_ids=scope["obs_ids"] or (0,))),
        ("其他 MSA工作流決策 引用 smoke 研究",
         'SELECT count(*) FROM "MSA工作流決策" WHERE "研究ID" IN :ids AND "識別碼" NOT IN :decision_ids',
         dict(ids=scope["study_ids"] or (0,), decision_ids=scope["decision_ids"] or (0,))),
        ("其他 MSA再研究要求 引用 smoke 研究",
         'SELECT count(*) FROM "MSA再研究要求" WHERE ("來源研究ID" IN :ids OR "新研究ID" IN :ids) AND "識別碼" NOT IN :restudy_ids',
         dict(ids=scope["study_ids"] or (0,), restudy_ids=scope["restudy_ids"] or (0,))),
        ("其他 MSA計畫版本 引用 smoke 研究",
         'SELECT count(*) FROM "MSA計畫版本" WHERE "研究ID" IN :ids AND "識別碼" NOT IN :plan_ids',
         dict(ids=scope["study_ids"] or (0,), plan_ids=scope["plan_ids"] or (0,))),
        ("其他 MSA研究設備 引用 smoke 研究",
         'SELECT count(*) FROM "MSA研究設備" WHERE "研究ID" IN :ids AND "識別碼" NOT IN :study_equip_ids',
         dict(ids=scope["study_ids"] or (0,), study_equip_ids=scope["study_equip_ids"] or (0,))),
    ]
    for name, sql, params in orphan_checks:
        got = _q1(sql, **params)
        status = "OK(0)" if got == 0 else f"異常({got})"
        lines.append(f"  [{status}] {name}")
        if got:
            raise RuntimeError(f"前檢核失敗：{name} 存在 {got} 筆未納入刪除範圍的資料")


def _delete(table: str, where: str, params: dict, lines: list[str]) -> int:
    """執行 DELETE 並回報筆數。"""
    result = db.session.execute(
        text(f'DELETE FROM "{table}" {where}'), params
    )
    lines.append(f"  DELETE {table}: {result.rowcount} 筆")
    return result.rowcount


def main(apply: bool) -> int:
    rc = 0
    with app.app_context():
        lines = []
        storage = app.config.get("STORAGE")
        att_paths: list[str] = []

        db.session.rollback()
        scope = _collect_scope()
        if not any(scope.values()):
            print("無任何 smoke 資料（SMOKE-% 前綴）可清除。")
            return 0

        triggers = _collect_triggers()
        try:
            _run_checks(scope, lines)

            lines.append(MSG_LINE)
            lines.append("刪除")
            lines.append(MSG_LINE)

            if not apply:
                lines.append("  （dry-run：未實際刪除，加 --apply 才會執行）")
            else:
                # ---------- 停用觸發器 ----------
                lines.append(f"停用觸發器（{len(triggers)} 個）")
                for table, tname, _ in triggers:
                    lines.append(f"  DISABLE {table}.{tname}")
                _set_triggers(triggers, enable=False)

                try:
                    # 1. MSA（最深子表先刪）
                    _delete("MSA觀測", 'WHERE "計畫版本ID" IN :ids', {"ids": scope["plan_ids"] or (0,)}, lines)
                    _delete("MSA觀測匯入批次", 'WHERE "計畫版本ID" IN :ids', {"ids": scope["plan_ids"] or (0,)}, lines)
                    _delete("MSA結果版本", 'WHERE "研究ID" IN :study_ids OR "計畫版本ID" IN :plan_ids',
                            {"study_ids": scope["study_ids"] or (0,), "plan_ids": scope["plan_ids"] or (0,)}, lines)
                    _delete("MSA工作流決策", 'WHERE "研究ID" IN :ids', {"ids": scope["study_ids"] or (0,)}, lines)
                    _delete("MSA再研究要求", 'WHERE "來源研究ID" IN :ids OR "新研究ID" IN :ids',
                            {"ids": scope["study_ids"] or (0,)}, lines)
                    _delete("MSA零件", 'WHERE "計畫版本ID" IN :ids', {"ids": scope["plan_ids"] or (0,)}, lines)
                    _delete("MSA評價人", 'WHERE "計畫版本ID" IN :ids', {"ids": scope["plan_ids"] or (0,)}, lines)
                    _delete("MSA研究設備", 'WHERE "研究ID" IN :ids', {"ids": scope["study_ids"] or (0,)}, lines)
                    db.session.execute(
                        text('UPDATE "MSA研究" SET "目前計畫版本ID" = NULL, "目前結果版本ID" = NULL WHERE "識別碼" IN :ids'),
                        {"ids": scope["study_ids"] or (0,)},
                    )
                    lines.append("  UPDATE MSA研究 釋放 目前計畫/結果版本ID")
                    _delete("MSA計畫版本", 'WHERE "識別碼" IN :ids', {"ids": scope["plan_ids"] or (0,)}, lines)
                    _delete("MSA研究", 'WHERE "識別碼" IN :ids', {"ids": scope["study_ids"] or (0,)}, lines)
                    db.session.execute(
                        text('UPDATE "MSA準則設定" SET "目前啟用版本ID" = NULL WHERE "識別碼" IN :ids'),
                        {"ids": scope["criteria_ids"] or (0,)},
                    )
                    lines.append("  UPDATE MSA準則設定 釋放 目前啟用版本ID")
                    _delete("MSA準則版本", 'WHERE "識別碼" IN :ids', {"ids": scope["criteria_ver_ids"] or (0,)}, lines)
                    _delete("MSA準則設定", 'WHERE "識別碼" IN :ids', {"ids": scope["criteria_ids"] or (0,)}, lines)

                    # 2. 校驗（子表先刪）
                    _delete("設備校正原始讀值", 'WHERE "設備校正點ID" IN (SELECT "識別碼" FROM "設備校正點" WHERE "校驗紀錄ID" IN :ids)',
                            {"ids": scope["rec_ids"] or (0,)}, lines)
                    _delete("設備校正點", 'WHERE "校驗紀錄ID" IN :ids', {"ids": scope["rec_ids"] or (0,)}, lines)
                    _delete("校正參考標準器快照", 'WHERE "校驗紀錄ID" IN :ids OR "核准校驗紀錄ID" IN :ids',
                            {"ids": scope["rec_ids"] or (0,)}, lines)
                    if scope["corr_ids"]:
                        _delete("設備校驗補正點", 'WHERE "識別碼" IN :ids', {"ids": scope["corr_ids"]}, lines)
                    # 捕捉附件實體檔路徑（commit 後刪除）
                    att_paths = [
                        row[0] for row in _rows(
                            'SELECT "檔案路徑" FROM "附件" WHERE "識別碼" IN :ids',
                            ids=scope["att_ids"] or (0,),
                        )
                    ]
                    db.session.execute(
                        text('UPDATE "設備校驗紀錄" SET "原始證書附件ID" = NULL WHERE "識別碼" IN :ids'),
                        {"ids": scope["rec_ids"] or (0,)},
                    )
                    lines.append("  UPDATE 設備校驗紀錄 釋放 原始證書附件ID")
                    _delete("附件", 'WHERE "識別碼" IN :ids', {"ids": scope["att_ids"] or (0,)}, lines)
                    _delete("設備校驗紀錄", 'WHERE "識別碼" IN :ids', {"ids": scope["rec_ids"] or (0,)}, lines)

                    # 3. 模板
                    db.session.execute(
                        text('UPDATE "校正模板" SET "目前核准版本ID" = NULL WHERE "識別碼" IN :ids'),
                        {"ids": scope["tpl_ids"] or (0,)},
                    )
                    lines.append("  UPDATE 校正模板 釋放 目前核准版本ID")
                    _delete("校正模板校正點", 'WHERE "識別碼" IN :ids', {"ids": scope["tpl_point_ids"] or (0,)}, lines)
                    _delete("校正模板版本", 'WHERE "識別碼" IN :ids', {"ids": scope["ver_ids"] or (0,)}, lines)
                    _delete("校正模板", 'WHERE "識別碼" IN :ids', {"ids": scope["tpl_ids"] or (0,)}, lines)

                    # 4. 設備
                    _delete("設備狀態事件", 'WHERE "設備ID" IN :ids', {"ids": scope["eq_ids"] or (0,)}, lines)
                    _delete("量測設備連結", 'WHERE "設備ID" IN :ids', {"ids": scope["eq_ids"] or (0,)}, lines)
                    _delete("設備匯入列", 'WHERE "對應設備ID" IN :ids', {"ids": scope["eq_ids"] or (0,)}, lines)
                    _delete("量測設備", 'WHERE "識別碼" IN :ids', {"ids": scope["eq_ids"] or (0,)}, lines)

                    # ---------- 事後驗證 ----------
                    lines.append(MSG_LINE)
                    lines.append("事後驗證")
                    lines.append(MSG_LINE)
                    verify = [
                        ("校正模板", 'SELECT count(*) FROM "校正模板" WHERE "識別碼" IN :ids', scope["tpl_ids"]),
                        ("校正模板版本", 'SELECT count(*) FROM "校正模板版本" WHERE "識別碼" IN :ids', scope["ver_ids"]),
                        ("校正模板校正點", 'SELECT count(*) FROM "校正模板校正點" WHERE "識別碼" IN :ids', scope["tpl_point_ids"]),
                        ("設備校驗紀錄", 'SELECT count(*) FROM "設備校驗紀錄" WHERE "識別碼" IN :ids', scope["rec_ids"]),
                        ("設備校正點", 'SELECT count(*) FROM "設備校正點" WHERE "校驗紀錄ID" IN :ids', scope["rec_ids"]),
                        ("設備校正原始讀值", 'SELECT count(*) FROM "設備校正原始讀值" WHERE "設備校正點ID" IN (SELECT "識別碼" FROM "設備校正點" WHERE "校驗紀錄ID" IN :ids)', scope["rec_ids"]),
                        ("校正參考標準器快照", 'SELECT count(*) FROM "校正參考標準器快照" WHERE "校驗紀錄ID" IN :ids OR "核准校驗紀錄ID" IN :ids', scope["rec_ids"]),
                        ("附件", 'SELECT count(*) FROM "附件" WHERE "識別碼" IN :ids', scope["att_ids"]),
                        ("量測設備", 'SELECT count(*) FROM "量測設備" WHERE "識別碼" IN :ids', scope["eq_ids"]),
                        ("MSA研究", 'SELECT count(*) FROM "MSA研究" WHERE "識別碼" IN :ids', scope["study_ids"]),
                        ("MSA研究設備", 'SELECT count(*) FROM "MSA研究設備" WHERE "研究ID" IN :ids', scope["study_ids"]),
                        ("MSA計畫版本", 'SELECT count(*) FROM "MSA計畫版本" WHERE "識別碼" IN :ids', scope["plan_ids"]),
                        ("MSA零件", 'SELECT count(*) FROM "MSA零件" WHERE "計畫版本ID" IN :ids', scope["plan_ids"]),
                        ("MSA評價人", 'SELECT count(*) FROM "MSA評價人" WHERE "計畫版本ID" IN :ids', scope["plan_ids"]),
                        ("MSA準則設定", 'SELECT count(*) FROM "MSA準則設定" WHERE "識別碼" IN :ids', scope["criteria_ids"]),
                        ("MSA準則版本", 'SELECT count(*) FROM "MSA準則版本" WHERE "識別碼" IN :ids', scope["criteria_ver_ids"]),
                    ]
                    all_clean = True
                    for name, sql, ids in verify:
                        params = {"ids": ids} if ids else {"ids": (0,)}
                        got = _q1(sql, **params)
                        status = "OK(0)" if got == 0 else f"殘留({got})"
                        lines.append(f"  [{status}] {name}")
                        if got:
                            all_clean = False
                    if not all_clean:
                        raise RuntimeError("事後驗證發現殘留資料，交易回滾")

                    db.session.commit()
                    lines.append(MSG_LINE)
                    lines.append("交易已提交，DB 清除完成")
                    lines.append(MSG_LINE)
                except Exception as exc:
                    db.session.rollback()
                    lines.append(MSG_LINE)
                    lines.append(f"!! 失敗，交易已回滾：{exc}")
                    lines.append(MSG_LINE)
                    rc = 1
                finally:
                    # ---------- 無論成敗，恢復觸發器 ----------
                    _set_triggers(triggers, enable=True)
                    lines.append(f"恢復觸發器（{len(triggers)} 個）")
                    for table, tname, _ in triggers:
                        lines.append(f"  ENABLE {table}.{tname}")
                    disabled = _q1(
                        """
                        SELECT count(*) FROM pg_trigger t
                        JOIN pg_class c ON c.oid = t.tgrelid
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE n.nspname = 'public'
                          AND c.relname IN :tables
                          AND t.tgname IS NOT NULL
                          AND NOT t.tgisinternal
                          AND t.tgenabled = 'D'
                        """,
                        tables=TARGET_TABLES,
                    )
                    if disabled:
                        lines.append(f"  [警告] 仍有 {disabled} 個觸發器處於停用狀態！")
                        rc = rc or 2
                    else:
                        lines.append("  [OK] 目標表觸發器全部恢復啟用")

        except Exception as exc:
            lines.append(MSG_LINE)
            lines.append(f"!! 前檢核失敗：{exc}")
            lines.append(MSG_LINE)
            rc = 1

        # ---------- 附件實體檔（commit 成功後刪除） ----------
        if rc == 0 and apply and att_paths:
            lines.append("附件實體檔")
            for rel in att_paths:
                if storage is None:
                    lines.append(f"  [警告] 無 STORAGE 設定，未刪除 {rel}")
                    continue
                existed = storage.get_abs_path(rel) is not None
                try:
                    storage.delete(rel)
                    lines.append(f"  [{'已刪除' if existed else '不存在(略過)'}] {rel}")
                except Exception as exc:
                    lines.append(f"  [失敗] {rel}: {exc}")
                    rc = 1

    print("\n".join(lines))
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main(apply="--apply" in sys.argv))

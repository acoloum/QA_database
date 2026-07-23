from backend.models import Vendor, VendorToleranceMain, VendorToleranceDetail, MechanicalTest
from backend.services.mechanical_service import MechanicalService


def _seed_spec(db_session):
    v = Vendor(name="安泰")
    db_session.add(v); db_session.flush()
    main = VendorToleranceMain(vendor_id=v.id, material="6061-T651", spec="36*25.2")
    db_session.add(main); db_session.flush()
    db_session.add(VendorToleranceDetail(main_id=main.id, item="洛氏硬度", tolerance_min=60, unit=""))
    db_session.commit()


def _payload():
    return {
        "產品尺寸": "36x25.2",
        "材質": "6061-T651",
        "測試日期": "2026-01-20",
        "T4溫度時間": "530/40MIN",
        "T6溫度時間": "175/6HR",
        "batches": [
            {"序號": 1, "擠製編號": "010761 D35", "爐具編號": "011313T42"},
            {"序號": 2, "擠製編號": "010851 D35", "爐具編號": "011314T42"},
        ],
        "measurements": [
            {"量測項目": "硬度", "測量位置": "爐門", "取樣序": 1, "量測值": 59},
            {"量測項目": "硬度", "測量位置": "爐頂", "取樣序": 1, "量測值": 73},
        ],
    }


def test_create_computes_ng_from_spec(db_session):
    _seed_spec(db_session)
    new_id = MechanicalService.create(_payload(), user_id=None)
    row = db_session.get(MechanicalTest, new_id)
    assert row is not None
    # 爐門 59 < 下限 60 → 該明細 NG，主檔 NG
    assert row.is_ng is True
    ng_items = [(m.location, m.is_ng) for m in row.measurements if m.item == "硬度"]
    assert ("爐門", True) in ng_items
    assert ("爐頂", False) in ng_items


def test_create_without_spec_is_not_ng(db_session):
    # 無規格 → 不判定
    new_id = MechanicalService.create(_payload(), user_id=None)
    row = db_session.get(MechanicalTest, new_id)
    assert row.is_ng is False
    assert all(m.is_ng is False for m in row.measurements)


def test_list_filters_by_size(db_session):
    MechanicalService.create(_payload(), user_id=None)
    res = MechanicalService.list({"product_size": "36"})
    assert res["total"] == 1
    assert res["data"][0]["產品尺寸"] == "36x25.2"
    res2 = MechanicalService.list({"product_size": "99"})
    assert res2["total"] == 0


def test_update_recomputes_ng(db_session):
    _seed_spec(db_session)
    new_id = MechanicalService.create(_payload(), user_id=None)
    payload = _payload()
    payload["measurements"][0]["量測值"] = 70  # 爐門改為 70 ≥ 60 → 不再 NG
    MechanicalService.update(new_id, payload, user_id=None)
    row = db_session.get(MechanicalTest, new_id)
    assert row.is_ng is False


def test_update_twice_with_same_measurement_keys_does_not_raise(db_session):
    """量測明細的 (量測項目, 測量位置, 取樣序) 鍵值不變、僅量測值變動時，
    連續更新兩次應能正確覆蓋量測值（功能面驗證：相同鍵值、值不同，重複更新皆正確）。

    注意：本測試「不能」也「沒有」鎖定 _apply_measurements／_apply_batches 的
    flush() 修正所要防範的那個 bug——該 IntegrityError 只在 PostgreSQL
    （不可延遲的唯一鍵，逐語句檢查）才會於 clear() 後、重新 append 前的同一次
    flush 中因排序不定而觸發；測試在 SQLite 記憶體資料庫上執行（見
    backend/tests/conftest.py），並不會重現此排序問題，因此拿掉 flush() 這
    支測試仍會通過。對正式環境該 bug 的實際防護，來自原始碼中確實存在
    db.session.flush() 這兩行，須以程式碼審查確認，而非本測試的通過與否。"""
    _seed_spec(db_session)
    new_id = MechanicalService.create(_payload(), user_id=None)

    payload = _payload()
    payload["measurements"][0]["量測值"] = 61  # 鍵值不變，僅改量測值
    MechanicalService.update(new_id, payload, user_id=None)

    payload2 = _payload()
    payload2["measurements"][0]["量測值"] = 62  # 再次以相同鍵值更新
    MechanicalService.update(new_id, payload2, user_id=None)

    row = db_session.get(MechanicalTest, new_id)
    values = {(m.item, m.location, m.sample_no): m.value for m in row.measurements}
    assert values[("硬度", "爐門", 1)] == 62
    assert values[("硬度", "爐頂", 1)] == 73


def test_get_detail_and_delete(db_session):
    new_id = MechanicalService.create(_payload(), user_id=None)
    detail = MechanicalService.get_detail(new_id)
    assert detail["main"]["產品尺寸"] == "36x25.2"
    assert len(detail["measurements"]) == 2
    # 批次保留 2 組並依序號排序
    assert [b["擠製編號"] for b in detail["batches"]] == ["010761 D35", "010851 D35"]
    assert detail["batches"][0]["爐具編號"] == "011313T42"
    MechanicalService.delete(new_id)
    assert db_session.get(MechanicalTest, new_id) is None

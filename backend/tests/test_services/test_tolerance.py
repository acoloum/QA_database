
import pytest
from datetime import datetime
from backend.services.tolerance_service import ToleranceService
from backend.models import VendorToleranceMain, VendorToleranceDetail, Vendor

def test_add_tolerance(app, db_session):
    with app.app_context():
        # Setup Vendor
        v = Vendor(name="Test Vendor")
        db_session.add(v)
        db_session.commit()

        data = {
            "材質": "SS400",
            "規格": "100*100",
            "廠商ID": v.id,
            "備註": "Test Note",
            "建立日期": datetime.now(),
            "details": [
                {
                    "測量項目": "OD",
                    "測量位置": "Pos1",
                    "尺寸下限": 9.9,
                    "尺寸上限": 10.1,
                    "公差下限": -0.1,
                    "公差上限": 0.1,
                    "標準值": 10.0,
                    "單位": "mm",
                    "備註": "Detail Note"
                }
            ]
        }
        
        new_id = ToleranceService.add_tolerance(data)
        assert new_id is not None
        
        # Verify DB
        t = db_session.get(VendorToleranceMain, new_id)
        assert t.material == "SS400"
        assert len(t.details) == 1
        assert t.details[0].item == "OD"

def test_check_tolerance_match(app, db_session):
    with app.app_context():
        # Setup Data
        v1 = Vendor(name="Vendor A")
        db_session.add(v1)
        db_session.flush()
        
        # Case 1: Exact Match
        t1 = VendorToleranceMain(material="SUS304", spec="10*10", vendor_id=v1.id)
        db_session.add(t1)
        
        # Case 2: Partial Spec Match (Wildcard logic handled in code check_tolerance)
        # Service logic: input_spec.startswith(t_spec + '*')
        
        db_session.commit()
        
        # Test Exact Match
        args = {"material": "SUS304", "spec": "10*10", "vendor_id": v1.id}
        result = ToleranceService.check_tolerance(args)
        assert result["success"] is True
        assert result["found"] is True
        assert result["tolerance_id"] == t1.id
        assert result["matched_priority"] == 1 # Priority 1: Same Vendor + Same Material + Same Spec

def test_check_tolerance_not_found(app, db_session):
    with app.app_context():
        args = {"material": "Unknown", "spec": "10*10"}
        result = ToleranceService.check_tolerance(args)
        assert result["success"] is True
        assert result["found"] is False


def test_search_tolerance_clamps_page_size(app, db_session):
    with app.app_context():
        result = ToleranceService.search_tolerance({"page_size": "5000"})
        assert result["page_size"] == 100


def test_tolerance_parse_spec_values_uses_shared_nominal_parser(app):
    """公差服務的規格解析應與共用解析器保持一致。"""
    with app.app_context():
        assert ToleranceService.parse_spec_values('31.9*2.2*589') == {
            '外徑': 31.9,
            '厚度': 2.2,
            '內徑': 27.5,
            '長度': 589.0,
        }


def test_tolerance_detail_roundtrips_characteristic_class(app, db_session):
    """特性重要度欄位應能透過 add_tolerance 寫入並經 get_tolerance_detail 讀出。"""
    with app.app_context():
        v = Vendor(name="Test Vendor CC")
        db_session.add(v)
        db_session.commit()

        data = {
            "材質": "TEST-CLS",
            "規格": "1*2*3",
            "廠商ID": v.id,
            "備註": "",
            "建立日期": datetime.now(),
            "details": [{
                "測量項目": "外徑", "測量位置": "",
                "尺寸下限": 1.0, "尺寸上限": 2.0,
                "公差下限": None, "公差上限": None,
                "標準值": None, "單位": "mm", "備註": "",
                "特性重要度": "關鍵",
            }],
        }
        new_id = ToleranceService.add_tolerance(data)
        got = ToleranceService.get_tolerance_detail(new_id)
        assert got["details"][0]["特性重要度"] == "關鍵"

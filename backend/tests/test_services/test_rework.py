
from datetime import datetime, date
import pytest
from backend.services.rework_service import ReworkService
from backend.models import ReworkInspection, ReworkRequest, NCMR, Inspector

def test_create_rework_application(app, db_session):
    with app.app_context():
        # Setup Prerequisites
        inspector = Inspector(name="Inspector A")
        db_session.add(inspector)
        
        ncmr = NCMR(ncmr_number="NCMR-001", product_info="Prod A", status="Open")
        db_session.add(ncmr)
        db_session.commit()

        data = {
            "NCMR_ID": ncmr.id,
            "申请人员姓名": "Inspector A", # Note: Service expects chinese key mapping from frontend?
            # Creating application usually comes from frontend JSON which maps fields.
            # Service create_application uses: data.get('申請人員姓名')
            "申請人員姓名": "Inspector A",
            "部門": "QA",
            "緊急程度": "High",
            "批號": "Batch001",
            "重工數量": 100,
            "申請原因": "Defect",
            "預計完成日期": date(2023, 12, 31)
        }

        result = ReworkService.create_application(data)
        assert result["rework_id"] is not None
        
        # Check Status Update
        assert ncmr.status == "轉重工"
        
        req = db_session.get(ReworkRequest, result["rework_id"])
        assert req.status == "申請中"
        assert req.rework_number.startswith("RW-")

def test_approve_application(app, db_session):
    with app.app_context():
        # Create Request
        inspector = Inspector(name="Manager B")
        db_session.add(inspector)
        req = ReworkRequest(status="申請中", rework_number="RW-Test")
        db_session.add(req)
        db_session.commit()
        
        data = {
            "rework_id": req.id,
            "action": "核准",
            "審核人員姓名": "Manager B",
            "opinion": "OK"
        }
        
        ReworkService.approve_application(data)
        
        assert req.status == "已核准"
        assert req.review_status == "已核准"
        assert req.reviewer_id == inspector.id

def test_execute_rework(app, db_session):
    with app.app_context():
         # Setup
        executor = Inspector(name="Worker C")
        db_session.add(executor)
        req = ReworkRequest(status="已核准", rework_number="RW-Exec")
        db_session.add(req)
        db_session.commit()
        
        data = {
            "重工單號": "RW-Exec",
            "負責人員姓名": "Worker C",
            "完成數量": 10,
            "不良數量": 0,
            "執行狀況": "Done"
        }
        
        ReworkService.create_execution(data)
        
        assert req.status == "執行中"
        assert len(req.executions) == 1
        assert req.executions[0].complete_qty == 10.0


def test_close_rework_requires_passed_final_inspection(app, db_session):
    with app.app_context():
        req = ReworkRequest(status="執行中", rework_number="RW-NoInspection")
        db_session.add(req)
        db_session.commit()

        with pytest.raises(ValueError, match="品檢合格"):
            ReworkService.close_rework({"rework_id": req.id})

        assert req.status == "執行中"


def test_close_rework_allows_passed_final_inspection(app, db_session):
    with app.app_context():
        inspector = Inspector(name="Inspector Pass")
        req = ReworkRequest(status="執行中", rework_number="RW-Passed")
        db_session.add_all([inspector, req])
        db_session.commit()

        db_session.add(ReworkInspection(
            rework_id=req.id,
            date=date(2026, 6, 20),
            inspector_id=inspector.id,
            item="最終品檢",
            result="合格",
            defect_qty=0,
        ))
        db_session.commit()

        ReworkService.close_rework({"rework_id": req.id})

        assert req.status == "已完成"

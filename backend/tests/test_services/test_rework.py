
from datetime import datetime, date
import json
import pytest
from backend.extensions import db
from backend.services.rework_service import ReworkService
from backend.models import (
    AuditLog, ReworkCost, ReworkExecution, ReworkInspection, ReworkRequest,
    NCMR, Inspector, User,
)
from backend.services.audit_service import AuditService
from backend.utils import generate_token

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

        result = ReworkService.create_application(data, actor_id=None)
        assert result["rework_id"] is not None
        
        # Check Status Update
        assert ncmr.status == "轉重工"
        
        req = db_session.get(ReworkRequest, result["rework_id"])
        assert req.status == "申請中"
        assert req.rework_number.startswith("RW-")


def test_create_rework_application_commits_in_service(app, db_session):
    with app.app_context():
        inspector = Inspector(name="Inspector No Commit")
        ncmr = NCMR(ncmr_number="NCMR-NOCOMMIT", product_info="Prod B", status="Open")
        db_session.add_all([inspector, ncmr])
        db_session.commit()

        result = ReworkService.create_application({
            "NCMR_ID": ncmr.id,
            "申請人員姓名": "Inspector No Commit",
            "部門": "QA",
            "緊急程度": "普通",
            "批號": "Batch002",
            "重工數量": 1,
            "申請原因": "Defect",
            "預計完成日期": date(2026, 6, 30),
        }, actor_id=None)

        assert result["rework_id"] is not None
        assert ncmr.status == "轉重工"


@pytest.mark.parametrize(
    'operation',
    [
        'apply', 'approve', 'close', 'delete',
        'execution_create', 'execution_update', 'execution_delete',
        'cost_create', 'cost_update', 'cost_delete',
        'inspection_create', 'inspection_update', 'inspection_delete',
    ],
)
@pytest.mark.parametrize('audit_fails', [True, False])
def test_rework_http_mutation_has_exact_audit_or_atomic_rollback(
    client, db_session, monkeypatch, operation, audit_fails
):
    """所有重工 mutation 的業務寫入與稽核必須共用同一交易。"""
    user = User(username=f'rework_atomic_{operation}', password='pw', role='admin', is_active=True)
    inspector = Inspector(name=f'人員-{operation}')
    ncmr = NCMR(ncmr_number=f'NCMR-{operation}', product_info='產品', status='Open')
    request_row = ReworkRequest(
        ncmr=ncmr,
        rework_number=f'RW-{operation}',
        applicant=inspector,
        status='執行中' if operation == 'close' else '申請中',
        review_status=None,
        quantity=10,
    )
    db_session.add_all([user, inspector, ncmr, request_row])
    db_session.flush()
    execution = ReworkExecution(
        rework_id=request_row.id,
        owner_id=inspector.id,
        executor_id=inspector.id,
        complete_qty=5,
        defect_qty=1,
        status='進行中',
    )
    cost = ReworkCost(
        rework_id=request_row.id,
        cost_type='人工成本',
        cost_item='原項目',
        unit_cost=10,
        quantity=2,
        total_cost=20,
        recorder_id=inspector.id,
    )
    inspection = ReworkInspection(
        rework_id=request_row.id,
        date=date(2026, 8, 1),
        inspector_id=inspector.id,
        item='最終品檢',
        result='合格',
        defect_qty=0,
        remark='原備註',
    )
    db_session.add_all([execution, cost, inspection])
    db_session.commit()
    ids = (request_row.id, execution.id, cost.id, inspection.id)
    token = generate_token(user.id, user.username, user.role, user.token_version)
    headers = {'Authorization': f'Bearer {token}'}

    def fail_audit(**_kwargs):
        raise RuntimeError('audit unavailable')

    if audit_fails:
        monkeypatch.setattr(AuditService, 'record', fail_audit)
    calls = {
        'apply': ('post', '/api/rework/apply', {
            'NCMR_ID': ncmr.id, '申請人員姓名': inspector.name,
            '重工數量': 1, '申請原因': '測試', 'password': 'TOP-SECRET',
        }),
        'approve': ('post', '/api/rework/approve', {
            'rework_id': request_row.id, 'action': '核准', '審核人員姓名': inspector.name,
        }),
        'close': ('post', '/api/rework/close', {'rework_id': request_row.id}),
        'delete': ('post', '/api/rework/delete', {'rework_id': request_row.id}),
        'execution_create': ('post', '/api/rework/execute', {
            '重工單號': request_row.rework_number, '負責人員姓名': inspector.name,
            '完成數量': 2, '不良數量': 0,
        }),
        'execution_update': ('put', f'/api/rework/execution/{execution.id}', {'執行狀況': '已完成'}),
        'execution_delete': ('delete', f'/api/rework/execution/{execution.id}', None),
        'cost_create': ('post', '/api/rework/cost', {
            '重工單號': request_row.rework_number, '記錄人員姓名': inspector.name,
            '成本類型': '材料成本', '成本項目': '新增', '單位成本': 3, '數量': 4,
        }),
        'cost_update': ('put', f'/api/rework/cost/{cost.id}', {'成本項目': '被修改'}),
        'cost_delete': ('delete', f'/api/rework/cost/{cost.id}', None),
        'inspection_create': ('post', '/api/rework/inspect', {
            '重工單號': request_row.rework_number, '檢驗人員姓名': inspector.name,
            '檢驗結果': '合格', '不良數量': 0,
        }),
        'inspection_update': ('put', f'/api/rework/inspection/{inspection.id}', {'檢驗備註': '被修改'}),
        'inspection_delete': ('delete', f'/api/rework/inspection/{inspection.id}', None),
    }
    method, url, payload = calls[operation]
    response = getattr(client, method)(url, json=payload, headers=headers)

    if not audit_fails:
        assert response.status_code == 200
        log = AuditLog.query.one()
        if operation in {'apply', 'approve', 'close', 'delete'}:
            module = '重工'
        elif operation.startswith('execution_'):
            module = '重工執行'
        elif operation.startswith('cost_'):
            module = '重工成本'
        else:
            module = '重工品檢'
        action = operation.split('_')[-1]
        if operation == 'apply':
            action = 'create'
        assert (log.user_id, log.action, log.module) == (user.id, action, module)
        assert len(log.action) <= 20
        assert 'TOP-SECRET' not in json.dumps(
            {'old': log.old_value, 'new': log.new_value}, ensure_ascii=False
        )
        return

    assert response.status_code == 500
    assert response.get_json()['error']['code'] == 'INTERNAL_ERROR'
    db_session.expire_all()
    persisted_request = db_session.get(ReworkRequest, ids[0])
    expected_status = '執行中' if operation == 'close' else '申請中'
    assert persisted_request.status == expected_status
    assert persisted_request.review_status is None
    assert persisted_request.deleted_at is None
    assert db_session.get(NCMR, ncmr.id).status == 'Open'
    assert db_session.get(ReworkExecution, ids[1]).status == '進行中'
    assert db_session.get(ReworkCost, ids[2]).cost_item == '原項目'
    assert db_session.get(ReworkInspection, ids[3]).remark == '原備註'
    assert ReworkRequest.query.count() == 1
    assert ReworkExecution.query.count() == 1
    assert ReworkCost.query.count() == 1
    assert ReworkInspection.query.count() == 1
    assert AuditLog.query.count() == 0


def test_rework_commit_failure_rolls_back_business_and_audit(
    client, db_session, monkeypatch
):
    """DB commit 失敗時，不得保留成本變更或稽核列。"""
    user = User(username='rework_commit_failure', password='pw', role='admin', is_active=True)
    inspector = Inspector(name='交易失敗記錄人')
    req = ReworkRequest(rework_number='RW-COMMIT-FAIL', status='申請中')
    db_session.add_all([user, inspector, req])
    db_session.flush()
    cost = ReworkCost(
        rework_id=req.id,
        cost_type='人工成本',
        cost_item='原值',
        unit_cost=10,
        quantity=1,
        total_cost=10,
        recorder_id=inspector.id,
    )
    db_session.add(cost)
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)

    def fail_commit():
        raise RuntimeError('database unavailable')

    monkeypatch.setattr(db.session, 'commit', fail_commit)
    response = client.put(
        f'/api/rework/cost/{cost.id}',
        json={'成本項目': '不得留下'},
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 500
    assert response.get_json()['error']['code'] == 'INTERNAL_ERROR'
    db_session.expire_all()
    assert db_session.get(ReworkCost, cost.id).cost_item == '原值'
    assert AuditLog.query.count() == 0


@pytest.mark.parametrize('operation', ['not_found', 'validation'])
def test_rework_domain_error_rolls_back_preexisting_pending_transaction(
    client, db_session, operation
):
    """查無資料與驗證錯誤也必須清除請求前已在 session 的待寫入資料。"""
    user = User(username=f'rework_pending_{operation}', password='pw', role='admin', is_active=True)
    req = ReworkRequest(rework_number=f'RW-PENDING-{operation}', status='申請中')
    db_session.add_all([user, req])
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)
    pending = NCMR(ncmr_number=f'NCMR-PENDING-{operation}', status='Open')
    db_session.add(pending)

    if operation == 'not_found':
        response = client.delete(
            '/api/rework/cost/999999',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 404
        assert response.get_json()['error']['code'] == 'NOT_FOUND'
    else:
        response = client.post(
            '/api/rework/approve',
            json={'rework_id': req.id, 'action': '未知動作'},
            headers={'Authorization': f'Bearer {token}'},
        )
        assert response.status_code == 400

    assert NCMR.query.filter_by(ncmr_number=pending.ncmr_number).count() == 0
    assert AuditLog.query.count() == 0


def test_rework_approval_rejects_invalid_state_without_writes(client, db_session):
    """執行中重工單不得逆向回到已核准。"""
    user = User(username='rework_invalid_state', password='pw', role='admin', is_active=True)
    inspector = Inspector(name='無效狀態審核人')
    req = ReworkRequest(rework_number='RW-INVALID-STATE', status='執行中')
    db_session.add_all([user, inspector, req])
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)

    response = client.post(
        '/api/rework/approve',
        json={'rework_id': req.id, 'action': '核准', '審核人員姓名': inspector.name},
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 400
    db_session.expire_all()
    assert db_session.get(ReworkRequest, req.id).status == '執行中'
    assert AuditLog.query.count() == 0

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
        
        ReworkService.approve_application(data, actor_id=None)
        
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
        
        ReworkService.create_execution(data, actor_id=None)
        
        assert req.status == "執行中"
        assert len(req.executions) == 1
        assert req.executions[0].complete_qty == 10.0


def test_close_rework_requires_passed_final_inspection(app, db_session):
    with app.app_context():
        req = ReworkRequest(status="執行中", rework_number="RW-NoInspection")
        db_session.add(req)
        db_session.commit()

        with pytest.raises(ValueError, match="品檢合格"):
            ReworkService.close_rework({"rework_id": req.id}, actor_id=None)

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

        ReworkService.close_rework({"rework_id": req.id}, actor_id=None)

        assert req.status == "已完成"


from datetime import datetime, date
import json
import pytest
from backend.extensions import db
from backend.services.rework_service import ReworkService
from backend.models import (
    AuditLog, ReworkCost, ReworkExecution, ReworkInspection, ReworkRequest,
    CustomerComplaint, NCMR, NcmrDisposition, Inspector, User,
)
from backend.services.audit_service import AuditService
from backend.services.ncmr_service import NCMRService
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


def test_create_second_execution_keeps_in_progress_and_writes_exact_audit(
    client, db_session
):
    """重工已執行中時可追加第二筆執行記錄，不需重複轉移狀態。"""
    user = User(username='rework_second_execution', password='pw', role='admin', is_active=True)
    inspector = Inspector(name='第二次執行人')
    req = ReworkRequest(rework_number='RW-SECOND-EXEC', status='執行中')
    db_session.add_all([user, inspector, req])
    db_session.flush()
    db_session.add(ReworkExecution(
        rework_id=req.id,
        owner_id=inspector.id,
        executor_id=inspector.id,
        complete_qty=2,
        defect_qty=0,
        status='已完成',
    ))
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)

    response = client.post(
        '/api/rework/execute',
        json={
            '重工單號': req.rework_number,
            '負責人員姓名': inspector.name,
            '完成數量': 3,
            '不良數量': 0,
            'password': 'SECOND-EXEC-SECRET',
        },
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(ReworkRequest, req.id).status == '執行中'
    assert ReworkExecution.query.filter_by(rework_id=req.id).count() == 2
    log = AuditLog.query.one()
    newest = ReworkExecution.query.filter_by(rework_id=req.id).order_by(ReworkExecution.id.desc()).first()
    assert (log.user_id, log.action, log.module, log.record_id) == (
        user.id, 'create', '重工執行', newest.id,
    )
    assert 'SECOND-EXEC-SECRET' not in json.dumps(log.new_value, ensure_ascii=False)


def test_create_execution_rejects_closed_rework_without_writes(client, db_session):
    """已結案重工單不可再新增執行記錄。"""
    user = User(username='rework_closed_execution', password='pw', role='admin', is_active=True)
    inspector = Inspector(name='結案後執行人')
    req = ReworkRequest(rework_number='RW-CLOSED-EXEC', status='已結案')
    db_session.add_all([user, inspector, req])
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)

    response = client.post(
        '/api/rework/execute',
        json={'重工單號': req.rework_number, '負責人員姓名': inspector.name},
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 400
    assert ReworkExecution.query.count() == 0
    assert AuditLog.query.count() == 0


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

        assert req.status == "已結案"


def test_close_rework_uses_ncmr_canonical_terminal_without_second_step(
    client, db_session
):
    """close API 必須一次進入 NCMR gate 認得的正式終態。"""
    user = User(username='rework_ncmr_close', password='pw', role='admin', is_active=True)
    inspector = Inspector(name='NCMR 重工結案品檢員')
    ncmr = NCMR(
        ncmr_number='NCMR-RW-CLOSE',
        status='矯正中',
        defect_quantity=5,
        quantity=5,
    )
    req = ReworkRequest(ncmr=ncmr, rework_number='RW-NCMR-CLOSE', status='執行中')
    db_session.add_all([user, inspector, ncmr, req])
    db_session.flush()
    db_session.add_all([
        ReworkInspection(
            rework_id=req.id,
            inspector_id=inspector.id,
            item='最終品檢',
            result='合格',
            defect_qty=0,
        ),
        NcmrDisposition(
            ncmr_id=ncmr.id,
            disposition_type='矯正重工',
            quantity=5,
            rework_id=req.id,
        ),
    ])
    db_session.commit()
    token = generate_token(user.id, user.username, user.role, user.token_version)

    response = client.post(
        '/api/rework/close',
        json={'rework_id': req.id},
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(ReworkRequest, req.id).status == '已結案'
    assert NCMRService.update_ncmr(
        {'識別碼': ncmr.id, '狀態': '已結案'}, actor_id=user.id
    ) is True
    assert db_session.get(NCMR, ncmr.id).status == '已結案'


def test_rework_apply_audit_contains_ncmr_source_transition_without_secret(app, db_session):
    """轉重工時，同一筆稽核須保留 NCMR 舊新狀態且排除自由文字。"""
    with app.app_context():
        secret = 'REWORK-APPLY-SOURCE-SECRET'
        inspector = Inspector(name='重工申請快照人員')
        ncmr = NCMR(
            ncmr_number='NCMR-RW-AUDIT-APPLY',
            product_info='產品',
            status='待處理',
            description=secret,
        )
        db_session.add_all([inspector, ncmr])
        db_session.commit()

        result = ReworkService.create_application({
            'NCMR_ID': ncmr.id,
            '申請人員姓名': inspector.name,
            '重工數量': 1,
            '申請原因': secret,
        }, actor_id=77)

        log = AuditLog.query.one()
        assert (log.user_id, log.action, log.module, log.record_id) == (
            77, 'create', '重工', result['rework_id'],
        )
        assert log.old_value == {
            'rework': None,
            'source': {
                'module': 'NCMR', 'id': ncmr.id, 'status': '待處理',
                'related_capa_id': None, 'related_capa_source': None,
                'deleted_at': None,
            },
        }
        assert log.new_value['source']['status'] == '轉重工'
        assert log.new_value['rework']['status'] == '申請中'
        assert secret not in json.dumps(
            {'old': log.old_value, 'new': log.new_value}, ensure_ascii=False,
        )


def test_rework_close_audit_contains_ncmr_source_transition_without_secret(app, db_session):
    """重工結案須在同一筆稽核記錄重工與 NCMR 的狀態轉移。"""
    with app.app_context():
        secret = 'REWORK-CLOSE-SOURCE-SECRET'
        inspector = Inspector(name='重工結案快照人員')
        ncmr = NCMR(
            ncmr_number='NCMR-RW-AUDIT-CLOSE', status='矯正中', description=secret,
        )
        req = ReworkRequest(
            ncmr=ncmr, rework_number='RW-AUDIT-CLOSE', status='執行中', reason=secret,
        )
        db_session.add_all([inspector, ncmr, req])
        db_session.flush()
        db_session.add(ReworkInspection(
            rework_id=req.id,
            inspector_id=inspector.id,
            item='最終品檢',
            result='合格',
            defect_qty=0,
        ))
        db_session.commit()

        ReworkService.close_rework({'rework_id': req.id}, actor_id=78)

        log = AuditLog.query.one()
        assert (log.user_id, log.action, log.module, log.record_id) == (
            78, 'close', '重工', req.id,
        )
        assert log.old_value['rework']['status'] == '執行中'
        assert log.new_value['rework']['status'] == '已結案'
        assert log.old_value['source']['status'] == '矯正中'
        assert log.new_value['source']['status'] == '矯正完成'
        assert secret not in json.dumps(
            {'old': log.old_value, 'new': log.new_value}, ensure_ascii=False,
        )


def test_rework_delete_audit_contains_complaint_unlink_without_secret(app, db_session):
    """刪除客訴來源重工時，稽核須包含解除連結與客訴狀態回退。"""
    with app.app_context():
        secret = 'REWORK-DELETE-COMPLAINT-SECRET'
        complaint = CustomerComplaint(
            complaint_no='CMP-RW-AUDIT-DELETE',
            customer='客戶',
            complaint_date=date(2026, 8, 1),
            description=secret,
            status='處理中',
        )
        req = ReworkRequest(
            complaint_id=None,
            rework_number='RW-AUDIT-DELETE',
            status='申請中',
            reason=secret,
        )
        db_session.add_all([complaint, req])
        db_session.flush()
        req.complaint_id = complaint.id
        complaint.related_rework_id = req.id
        db_session.commit()

        ReworkService.delete_rework(req.id, actor_id=79)

        log = AuditLog.query.one()
        assert (log.user_id, log.action, log.module, log.record_id) == (
            79, 'delete', '重工', req.id,
        )
        assert log.old_value['source'] == {
            'module': '客訴', 'id': complaint.id, 'status': '處理中',
            'related_capa_id': None, 'related_rework_id': req.id,
            'deleted_at': None,
        }
        assert log.new_value['source']['status'] == '待處理'
        assert log.new_value['source']['related_rework_id'] is None
        assert log.old_value['rework']['deleted_at'] is None
        assert log.new_value['rework']['deleted_at'] is not None
        assert secret not in json.dumps(
            {'old': log.old_value, 'new': log.new_value}, ensure_ascii=False,
        )


# ---------------------------------------------------------------------------
# get_statistics：條件式聚合（原本為多次 count/sum 分開查詢）的數值回歸
# ---------------------------------------------------------------------------

def _seed_statistics_fixture(db_session):
    """建立涵蓋各狀態、部門與成本類型的重工資料。"""
    requests = [
        ReworkRequest(rework_number='RW-ST-01', status='已結案', department='押出',
                      quantity=10, created_at=datetime(2026, 8, 5)),
        ReworkRequest(rework_number='RW-ST-02', status='已完成', department='押出',
                      quantity=20, created_at=datetime(2026, 8, 6)),
        ReworkRequest(rework_number='RW-ST-03', status='執行中', department='加工',
                      quantity=30, created_at=datetime(2026, 8, 7)),
        ReworkRequest(rework_number='RW-ST-04', status='已核准', department='加工',
                      quantity=40, created_at=datetime(2026, 8, 8)),
        ReworkRequest(rework_number='RW-ST-05', status='待審核', review_status='已拒絕',
                      department=None, quantity=50, created_at=datetime(2026, 8, 9)),
    ]
    db_session.add_all(requests)
    db_session.commit()
    return requests


def test_get_statistics_application_counts(app, db_session):
    """各狀態計數與總數量須與逐項 count/sum 的結果一致。"""
    with app.app_context():
        _seed_statistics_fixture(db_session)

        stats = ReworkService.get_statistics({})['application_stats']

        assert stats['total_applications'] == 5
        assert stats['completed'] == 2          # 已結案 + 已完成
        assert stats['in_progress'] == 1
        assert stats['approved'] == 1
        assert stats['rejected'] == 1
        assert stats['total_rework_quantity'] == 150.0


def test_get_statistics_respects_date_range_and_soft_delete(app, db_session):
    """期間條件與軟刪除排除須套用在同一組聚合上。"""
    with app.app_context():
        requests = _seed_statistics_fixture(db_session)
        requests[0].soft_delete()
        db_session.add(ReworkRequest(
            rework_number='RW-ST-OUT', status='執行中', department='押出',
            quantity=999, created_at=datetime(2026, 9, 1),
        ))
        db_session.commit()

        stats = ReworkService.get_statistics({
            'start_date': datetime(2026, 8, 1),
            'end_date': datetime(2026, 8, 31),
        })['application_stats']

        assert stats['total_applications'] == 4      # 5 筆扣掉軟刪除的 1 筆
        assert stats['completed'] == 1               # 已結案那筆被軟刪除
        assert stats['total_rework_quantity'] == 140.0


def test_get_statistics_department_breakdown(app, db_session):
    """部門統計須與期間條件共用同一組過濾條件。"""
    with app.app_context():
        _seed_statistics_fixture(db_session)

        dept_stats = ReworkService.get_statistics({})['department_stats']
        by_dept = {row['department']: row for row in dept_stats}

        assert by_dept['押出']['count'] == 2
        assert by_dept['押出']['quantity'] == 30.0
        assert by_dept['加工']['count'] == 2
        assert by_dept['加工']['quantity'] == 70.0
        assert by_dept['']['count'] == 1             # department 為 NULL 者歸入空字串


def test_get_statistics_cost_breakdown(app, db_session):
    """成本別彙總改為單一條件式聚合後，各項金額須不變。"""
    with app.app_context():
        requests = _seed_statistics_fixture(db_session)
        rework_id = requests[0].id
        db_session.add_all([
            ReworkCost(rework_id=rework_id, cost_type='人工成本', total_cost=100.5),
            ReworkCost(rework_id=rework_id, cost_type='人工成本', total_cost=200.0),
            ReworkCost(rework_id=rework_id, cost_type='材料成本', total_cost=300.0),
            ReworkCost(rework_id=rework_id, cost_type='設備成本', total_cost=400.0),
            ReworkCost(rework_id=rework_id, cost_type='其他', total_cost=50.0),
        ])
        db_session.commit()

        cost_stats = ReworkService.get_statistics({})['cost_stats']

        assert cost_stats['total_records'] == 5
        assert cost_stats['total_cost'] == 1050.5
        assert cost_stats['labor_cost'] == 300.5
        assert cost_stats['material_cost'] == 300.0
        assert cost_stats['equipment_cost'] == 400.0


def test_get_statistics_empty_dataset_returns_zeros(app, db_session):
    """無資料時聚合結果為 NULL，須轉成 0 而非 None。"""
    with app.app_context():
        stats = ReworkService.get_statistics({})

        assert stats['application_stats']['total_applications'] == 0
        assert stats['application_stats']['completed'] == 0
        assert stats['application_stats']['total_rework_quantity'] == 0
        assert stats['cost_stats']['total_cost'] == 0
        assert stats['cost_stats']['labor_cost'] == 0
        assert stats['department_stats'] == []

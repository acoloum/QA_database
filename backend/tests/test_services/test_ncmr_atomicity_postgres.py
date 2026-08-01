"""Task 7 的 PostgreSQL JSONB 與競態交易證據。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
import os
from threading import Barrier, BrokenBarrierError, Event, current_thread
from uuid import uuid4

import pytest
from flask import Flask
from sqlalchemy import create_engine, select, text

from backend.errors import APIError
from backend.extensions import db
from backend.models import (
    AuditLog,
    CorrectiveAction,
    Inspector,
    NCMR,
    NcmrDisposition,
    Role,
    User,
)
from backend.request_context import add_response_headers, before_request_context
from backend.routes.ncmr import ncmr_bp
from backend.services.audit_service import AuditService
from backend.services.capa_service import CAPAService
from backend.services.ncmr_service import NCMRService
from backend.utils import api_error, generate_token, hash_password


def _headers(user: User) -> dict[str, str]:
    token = generate_token(user.id, user.username, user.role, user.token_version)
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


@pytest.fixture
def postgres_atomicity_app():
    """只在具安全前綴的 PostgreSQL 18 隔離 DB 內建立 UUID schema。"""
    database_url = os.getenv('ATOMICITY_TEST_DATABASE_URL')
    if not database_url:
        pytest.skip('未設定 ATOMICITY_TEST_DATABASE_URL')

    root_engine = create_engine(database_url, pool_pre_ping=True)
    schema_name = f'atomicity7_{uuid4().hex}'
    pg_app = None
    app_engine = None
    try:
        with root_engine.connect() as connection:
            if connection.dialect.name != 'postgresql':
                pytest.fail('ATOMICITY_TEST_DATABASE_URL 必須指向 PostgreSQL')
            database_name = connection.execute(text('SELECT current_database()')).scalar_one()
            if not database_name.startswith('codex_atomicity7_'):
                pytest.fail('Task 7 只允許 codex_atomicity7_ 前綴隔離資料庫')
            server_major = connection.execute(
                text("SELECT current_setting('server_version_num')::integer / 10000")
            ).scalar_one()
            if server_major != 18:
                pytest.fail('Task 7 併發確效必須使用 PostgreSQL 18')
            connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
            connection.commit()

        pg_app = Flask(f'ncmr-atomicity-{schema_name}')
        pg_app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI=database_url,
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SQLALCHEMY_ENGINE_OPTIONS={
                'pool_pre_ping': True,
                'connect_args': {
                    'options': (
                        f'-csearch_path={schema_name},public '
                        '-cstatement_timeout=8000 -clock_timeout=4000'
                    ),
                },
            },
        )
        db.init_app(pg_app)
        pg_app.before_request(before_request_context)
        pg_app.after_request(add_response_headers)
        pg_app.register_blueprint(ncmr_bp)

        @pg_app.errorhandler(APIError)
        def handle_api_error(error):
            return api_error(
                error.message,
                error.status_code,
                code=error.code,
                details=error.details,
            )

        @pg_app.errorhandler(ValueError)
        def handle_value_error(error):
            return api_error(str(error), 400, code='VALIDATION_ERROR')

        @pg_app.errorhandler(Exception)
        def handle_unexpected_error(_error):
            return api_error('伺服器內部錯誤', 500, code='INTERNAL_ERROR')

        with pg_app.app_context():
            db.create_all()
            edit_owner = Inspector(name='PG 原擁有人')
            revoked_owner = Inspector(name='PG 新擁有人')
            db.session.add_all([edit_owner, revoked_owner])
            db.session.flush()
            db.session.add_all([
                Role(
                    code='pg_ncmr_full',
                    name='PG NCMR 完整權限',
                    permissions={
                        'ncmr.edit': True,
                        'capa.create': True,
                        'ncmr.disposition': True,
                    },
                ),
                Role(
                    code='pg_ncmr_own',
                    name='PG NCMR 本人權限',
                    permissions={'ncmr.edit_own': True},
                ),
            ])
            full_user = User(
                username='pg_atomic_full',
                password=hash_password('atomic-password'),
                role='pg_ncmr_full',
                is_active=True,
            )
            own_user = User(
                username='pg_atomic_owner',
                password=hash_password('atomic-password'),
                role='pg_ncmr_own',
                inspector_id=edit_owner.id,
                is_active=True,
            )
            open_ncmr = NCMR(
                ncmr_number='NCMR-PG-OPEN',
                date=date(2026, 8, 1),
                source='進料',
                description='PG open CAPA',
                defect_quantity=1,
                quantity=1,
                status='待處理',
            )
            edit_ncmr = NCMR(
                ncmr_number='NCMR-PG-EDIT',
                date=date(2026, 8, 1),
                source='進料',
                description='撤銷前內容',
                inspector_id=edit_owner.id,
                defect_quantity=1,
                status='待處理',
            )
            close_ncmr = NCMR(
                ncmr_number='NCMR-PG-CLOSE',
                date=date(2026, 8, 1),
                source='進料',
                description='close race',
                defect_quantity=100,
                status='待處理',
            )
            db.session.add_all([full_user, own_user, open_ncmr, edit_ncmr, close_ncmr])
            db.session.flush()
            close_disposition = NcmrDisposition(
                ncmr_id=close_ncmr.id,
                disposition_type='報廢',
                quantity=100,
            )
            db.session.add(close_disposition)
            db.session.commit()
            identifiers = {
                'full_headers': _headers(full_user),
                'own_headers': _headers(own_user),
                'open_id': open_ncmr.id,
                'edit_id': edit_ncmr.id,
                'close_id': close_ncmr.id,
                'close_disposition_id': close_disposition.id,
                'revoked_owner_id': revoked_owner.id,
            }
            app_engine = db.engine

        yield pg_app, app_engine, schema_name, identifiers
    finally:
        if pg_app is not None:
            with pg_app.app_context():
                db.session.remove()
                db.engine.dispose()
        try:
            with root_engine.connect() as connection:
                database_name = connection.execute(
                    text('SELECT current_database()')
                ).scalar_one()
                if not database_name.startswith('codex_atomicity7_'):
                    pytest.fail('cleanup guard 拒絕非隔離資料庫')
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
                connection.commit()
        finally:
            root_engine.dispose()


def _join(futures, timeout=12):
    results = []
    for future in futures:
        results.append(future.result(timeout=timeout))
    return results


def test_postgresql_open_capa_serializes_duplicate_http_requests(
    postgres_atomicity_app, monkeypatch
):
    app, _engine, _schema, identifiers = postgres_atomicity_app
    both_routes_prechecked = Barrier(2)
    original = CAPAService.open_from_ncmr

    def synchronized_open(*args, **kwargs):
        try:
            both_routes_prechecked.wait(timeout=5)
        except BrokenBarrierError as error:
            raise TimeoutError('兩個 open CAPA 請求未同時到達 service') from error
        return original(*args, **kwargs)

    monkeypatch.setattr(CAPAService, 'open_from_ncmr', synchronized_open)

    def post_open():
        with app.test_client() as client:
            response = client.post(
                f"/api/ncmr/{identifiers['open_id']}/open-capa",
                headers=identifiers['full_headers'],
                json={'severity': 'Major'},
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = _join([executor.submit(post_open), executor.submit(post_open)])

    assert sorted(statuses) == [201, 409]
    with app.app_context():
        ncmr = db.session.get(NCMR, identifiers['open_id'])
        capas = CorrectiveAction.query.filter_by(
            source_type='ncmr', source_id=ncmr.id
        ).all()
        assert len(capas) == 1
        assert AuditLog.query.filter_by(module='CAPA', action='create').count() == 1
        assert ncmr.related_capa_id == capas[0].id


def test_postgresql_edit_own_rechecks_locked_latest_owner_before_mutation(
    postgres_atomicity_app, monkeypatch
):
    app, engine, schema_name, identifiers = postgres_atomicity_app
    route_reached_service = Event()
    ownership_revoked = Event()
    original = NCMRService.update_ncmr

    def pause_before_service(*args, **kwargs):
        route_reached_service.set()
        if not ownership_revoked.wait(timeout=5):
            raise TimeoutError('等待 ownership 撤銷逾時')
        return original(*args, **kwargs)

    monkeypatch.setattr(NCMRService, 'update_ncmr', pause_before_service)

    def update_as_old_owner():
        with app.test_client() as client:
            response = client.post(
                '/api/ncmr/update',
                headers=identifiers['own_headers'],
                json={
                    '識別碼': identifiers['edit_id'],
                    '不良描述': '不應寫入',
                },
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(update_as_old_owner)
        assert route_reached_service.wait(timeout=5)
        with engine.begin() as connection:
            connection.execute(text(f'SET search_path TO "{schema_name}", public'))
            connection.execute(
                text(
                    'UPDATE "不合格品單" SET "發現人員" = :owner_id '
                    'WHERE "識別碼" = :ncmr_id'
                ),
                {
                    'owner_id': identifiers['revoked_owner_id'],
                    'ncmr_id': identifiers['edit_id'],
                },
            )
        ownership_revoked.set()
        status = future.result(timeout=10)

    assert status == 403
    with app.app_context():
        db.session.expire_all()
        ncmr = db.session.get(NCMR, identifiers['edit_id'])
        assert ncmr.description == '撤銷前內容'
        assert AuditLog.query.filter_by(module='NCMR', record_id=ncmr.id).count() == 0


def test_postgresql_close_serializes_against_disposition_update(
    postgres_atomicity_app, monkeypatch
):
    app, _engine, _schema, identifiers = postgres_atomicity_app
    close_at_audit = Event()
    allow_close_commit = Event()
    mutation_entered = Event()
    mutation_done = Event()
    original_record = AuditService.record
    original_update = NCMRService.update_disposition

    def pause_close_audit(**kwargs):
        entry = original_record(**kwargs)
        if (
            current_thread().name == 'pg-close'
            and kwargs.get('module') == 'NCMR'
            and kwargs.get('action') == 'update'
        ):
            close_at_audit.set()
            if not allow_close_commit.wait(timeout=5):
                raise TimeoutError('等待 close commit 放行逾時')
        return entry

    def mark_mutation(*args, **kwargs):
        mutation_entered.set()
        return original_update(*args, **kwargs)

    monkeypatch.setattr(AuditService, 'record', pause_close_audit)
    monkeypatch.setattr(NCMRService, 'update_disposition', mark_mutation)

    def close_ncmr():
        current_thread().name = 'pg-close'
        with app.test_client() as client:
            response = client.post(
                '/api/ncmr/update',
                headers=identifiers['full_headers'],
                json={'識別碼': identifiers['close_id'], '狀態': '已結案'},
            )
            return response.status_code

    def update_disposition():
        try:
            with app.test_client() as client:
                response = client.put(
                    f"/api/ncmr/dispositions/{identifiers['close_disposition_id']}",
                    headers=identifiers['full_headers'],
                    json={'處置類型': '報廢', '處置數量': 50},
                )
                return response.status_code
        finally:
            mutation_done.set()

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='pg-worker') as executor:
        close_future = executor.submit(close_ncmr)
        assert close_at_audit.wait(timeout=5)
        mutation_future = executor.submit(update_disposition)
        assert mutation_entered.wait(timeout=5)
        completed_before_release = mutation_done.wait(timeout=0.5)
        allow_close_commit.set()
        close_status = close_future.result(timeout=10)
        mutation_status = mutation_future.result(timeout=10)

    assert completed_before_release is False
    assert close_status == 200
    assert mutation_status == 400
    with app.app_context():
        db.session.expire_all()
        ncmr = db.session.get(NCMR, identifiers['close_id'])
        disposition = db.session.get(
            NcmrDisposition, identifiers['close_disposition_id']
        )
        assert ncmr.status == '已結案'
        assert disposition.quantity == ncmr.defect_quantity == 100
        assert AuditLog.query.filter_by(
            module='NCMR_DISPOSITION', action='update'
        ).count() == 0


def test_postgresql_audit_jsonb_accepts_non_finite_float_markers(
    postgres_atomicity_app,
):
    app, _engine, _schema, _identifiers = postgres_atomicity_app
    with app.app_context():
        entry = AuditService.record(
            actor_id=None,
            action='create',
            module='NCMR',
            record_id=999,
            new_value={
                'nan': float('nan'),
                'positive': float('inf'),
                'negative': float('-inf'),
            },
        )
        db.session.commit()
        stored = db.session.scalar(select(AuditLog).where(AuditLog.id == entry.id))
        assert stored.new_value == {
            'nan': '[NON_FINITE_FLOAT:NaN]',
            'positive': '[NON_FINITE_FLOAT:Infinity]',
            'negative': '[NON_FINITE_FLOAT:-Infinity]',
        }


import pytest
import os

# Patch configuration BEFORE importing app
import backend.config
backend.config.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
backend.config.SQLALCHEMY_TRACK_MODIFICATIONS = False
# SQLite 不支援 pool_size / max_overflow，測試時改用最小設定
backend.config.SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_pre_ping': True,
}

from backend.app import app as flask_app
from backend.extensions import db
from backend.models import (
    User, Inspector, Vendor, Machine, Operator,
    Role,
)
from backend.utils import generate_token


@pytest.fixture
def app():
    flask_app.config["TESTING"] = True
    
    with flask_app.app_context():
        # Ensure proper engine disposal just in case
        db.engine.dispose()
        
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db.session
        db.session.rollback()


@pytest.fixture
def setup_data(db_session):
    """Pre-populate common data for tests"""
    # Create Inspector
    inspector = Inspector(name="Test Inspector")
    db_session.add(inspector)
    
    # Create Vendor
    vendor = Vendor(name="Test Vendor")
    db_session.add(vendor)
    
    # Create User
    user = User(username="testuser", password="password") # Hash if needed, but for unit tests maybe simple? 
    # Logic uses hash_password, so maybe we need to mock or hash it if we test auth.
    # For Service tests we might bypass auth or mock it.
    db_session.add(user)
    
    db_session.commit()
    
    return {
        "inspector_id": inspector.id,
        "vendor_id": vendor.id,
        "user_id": user.id
    }


@pytest.fixture
def calibration_users(db_session):
    """建立校正測試用的使用者角色與帳號。"""
    roles = [
        Role(
            code="cal_viewer",
            name="校正檢視者",
            permissions={"calibration.view": True},
        ),
        Role(
            code="cal_manager",
            name="校正管理者",
            permissions={
                "calibration.view": True,
                "calibration.execute": True,
                "calibration.manage": True,
                "calibration.approve": True,
            },
        ),
        Role(
            code="cal_approver",
            name="校正核准者",
            permissions={
                "calibration.view": True,
                "calibration.approve": True,
            },
        ),
        Role(
            code="cal_no_permission",
            name="無校正權限",
            permissions={"msa.manage": True},
        ),
    ]
    db_session.add_all(roles)
    users = {}
    for key, role, active in [
        ("viewer", "cal_viewer", True),
        ("manager", "cal_manager", True),
        ("approver", "cal_approver", True),
        ("no_permission", "cal_no_permission", True),
        ("inactive_manager", "cal_manager", False),
    ]:
        user = User(
            username=f"cal_{key}",
            password="test-password",
            role=role,
            is_active=active,
        )
        db_session.add(user)
        users[key] = user
    db_session.commit()
    return {
        key: {
            "user": user,
            "token": generate_token(
                user.id, user.username, user.role, user.token_version
            ),
        }
        for key, user in users.items()
    }

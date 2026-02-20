
import pytest
import os

# Patch configuration BEFORE importing app
import backend.config
backend.config.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
backend.config.SQLALCHEMY_TRACK_MODIFICATIONS = False

from backend.app import app as flask_app
from backend.extensions import db
from backend.models import User, Inspector, Vendor, Machine, Operator

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

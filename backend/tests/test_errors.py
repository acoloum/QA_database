
import pytest
from unittest.mock import patch
from backend.errors import APIError
from backend.utils import generate_token

@pytest.fixture
def auth_headers():
    token = generate_token(user_id=1, username="testuser")
    return {'Authorization': f'Bearer {token}'}

def test_api_error_handler(app, client, auth_headers):
    """Test standard APIError handling"""
    # Ensure handlers are triggered
    app.config['PROPAGATE_EXCEPTIONS'] = False
    
    # Patch a known existing route to raise APIError
    with patch('backend.services.tolerance_service.ToleranceService.search_tolerance') as mock_search:
        mock_search.side_effect = APIError("Custom Error", code="CUSTOM_ERR", status_code=418)
        
        # Call the route that uses this service
        response = client.get('/api/tolerance/search?material=test', headers=auth_headers)
        
        assert response.status_code == 418
        data = response.get_json()
        assert data["success"] is False
        assert data["error"]["code"] == "CUSTOM_ERR"
        assert data["error"]["message"] == "Custom Error"

def test_404_handler(client):
    """Test 404 handling for non-existent routes"""
    response = client.get('/non/existent/route')
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"

def test_generic_exception(app, client, auth_headers):
    """Test generic 500 exception handling"""
    # Ensure handlers are triggered
    app.config['PROPAGATE_EXCEPTIONS'] = False

    # Patch a known existing route to raise a generic unexpected exception
    with patch('backend.services.tolerance_service.ToleranceService.search_tolerance') as mock_search:
        mock_search.side_effect = RuntimeError("Something went wrong")
        
        response = client.get('/api/tolerance/search?material=test', headers=auth_headers)
        
        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"

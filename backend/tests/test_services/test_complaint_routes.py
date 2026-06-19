from backend.models import User
from backend.utils import generate_token


def test_complaint_list_route_clamps_per_page(client, db_session):
    user = User(username='complaint_list_user', password='pw', role='viewer', is_active=True)
    db_session.add(user)
    db_session.commit()
    token = generate_token(user.id, user.username, user.role)

    response = client.get('/api/complaints?per_page=5000', headers={'Authorization': f'Bearer {token}'})

    assert response.status_code == 200
    assert response.get_json()['per_page'] == 100

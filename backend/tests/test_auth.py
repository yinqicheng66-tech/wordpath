from sqlalchemy import select

from app.db import get_db
from app.models import User

EMAIL = "student@uwaterloo.ca"
PASSWORD = "correct-horse"


def register(client, email=EMAIL, password=PASSWORD):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_returns_token(client):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_register_duplicate_email_is_rejected(client):
    register(client)
    response = register(client, email=EMAIL.upper())  # emails are case-insensitive
    assert response.status_code == 409


def test_register_rejects_short_password(client):
    assert register(client, password="short").status_code == 422


def test_register_rejects_invalid_email(client):
    assert register(client, email="not-an-email").status_code == 422


def test_password_is_stored_hashed(client):
    register(client)
    # Open a session on the same test database the API used.
    db = next(client.app.dependency_overrides[get_db]())
    user = db.scalar(select(User).where(User.email == EMAIL))
    assert user.password_hash != PASSWORD
    assert user.password_hash.startswith("$2")  # bcrypt format
    db.close()


def test_login_with_correct_password(client):
    register(client)
    response = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_with_wrong_password(client):
    register(client)
    response = client.post("/api/auth/login", json={"email": EMAIL, "password": "wrong-pass"})
    assert response.status_code == 401


def test_login_with_unknown_email(client):
    response = client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    assert response.status_code == 401


def test_me_returns_current_user(client):
    token = register(client).json()["access_token"]
    response = client.get("/api/me", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json()["email"] == EMAIL


def test_me_without_token_is_unauthorized(client):
    assert client.get("/api/me").status_code == 401


def test_me_with_bad_token_is_unauthorized(client):
    response = client.get("/api/me", headers=auth_header("not-a-real-token"))
    assert response.status_code == 401

def test_register_and_login(client):
    resp = client.post("/auth/register", json={
        "email": "student@example.com",
        "password": "hunter22",
        "display_name": "Test Student",
    })
    assert resp.status_code == 201
    assert resp.json()["email"] == "student@example.com"

    resp = client.post("/auth/login", json={
        "email": "student@example.com",
        "password": "hunter22",
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    assert token

    resp = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "student@example.com"


def test_login_wrong_password(client):
    client.post("/auth/register", json={"email": "a@b.com", "password": "correct"})
    resp = client.post("/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert resp.status_code == 401


def test_me_requires_auth(client):
    resp = client.get("/users/me")
    assert resp.status_code == 401


def test_update_interests(client):
    client.post("/auth/register", json={"email": "c@d.com", "password": "pw123456"})
    token = client.post("/auth/login", json={"email": "c@d.com", "password": "pw123456"}).json()["access_token"]
    resp = client.patch(
        "/users/me",
        json={"interests": ["techno", "student", "free"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["interests"] == ["techno", "student", "free"]

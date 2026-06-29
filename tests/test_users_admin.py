import pytest

pytestmark = pytest.mark.django_db

USERS = "/api/v1/admin/users/"


def test_user_list_paginated_for_super_admin(superuser, auth):
    r = auth(superuser).get(USERS)
    assert r.status_code == 200
    assert "results" in r.data and "count" in r.data


def test_user_list_forbidden_for_normal(make_user, auth):
    assert auth(make_user()).get(USERS).status_code == 403


def test_create_user_then_assign_and_revoke_role(superuser, make_role, auth):
    make_role("employee")
    c = auth(superuser)

    created = c.post(USERS, {"mobile": "09121111111", "full_name": "تست"}, format="json")
    assert created.status_code == 201
    uid = created.data["id"]

    assigned = c.post(f"{USERS}{uid}/roles/", {"role_code": "employee"}, format="json")
    assert assigned.status_code == 201
    ur_id = assigned.data["id"]

    listed = c.get(f"{USERS}{uid}/roles/")
    assert any(x["role_code"] == "employee" for x in listed.data)

    revoked = c.post(f"{USERS}{uid}/revoke-role/", {"user_role_id": ur_id}, format="json")
    assert revoked.status_code == 204


def test_create_user_invalid_mobile(superuser, auth):
    r = auth(superuser).post(USERS, {"mobile": "123"}, format="json")
    assert r.status_code == 400


def test_create_user_duplicate_mobile(superuser, make_user, auth):
    make_user(mobile="09122222222")
    r = auth(superuser).post(USERS, {"mobile": "09122222222"}, format="json")
    assert r.status_code == 400


def test_audit_logins_accessible_to_super_admin(superuser, auth):
    assert auth(superuser).get("/api/v1/admin/audit/logins").status_code == 200

"""Tests for RBAC, current-user endpoints and super-admin user management."""
import pytest

pytestmark = pytest.mark.django_db


def test_me_requires_auth(api_client):
    assert api_client.get("/api/v1/me").status_code == 401


def test_me_roles(make_user, auth_client, rbac, assign_role):
    u = make_user(mobile="09120000001")
    assign_role(u, "employee")
    r = auth_client(u).get("/api/v1/me/roles")
    assert r.status_code == 200
    assert any(role["code"] == "employee" for role in r.data["roles"])
    assert "welfare.profile.view" in r.data["permissions"]


def test_users_list_permission(make_user, auth_client, rbac, assign_role, superuser):
    u = make_user(mobile="09120000002")
    assign_role(u, "employee")
    assert auth_client(u).get("/api/v1/admin/users").status_code == 403
    assert auth_client(superuser).get("/api/v1/admin/users").status_code == 200


def test_assign_role_via_api(make_user, auth_client, rbac, superuser):
    target = make_user(mobile="09120000003")
    r = auth_client(superuser).post(
        f"/api/v1/admin/users/{target.id}/roles",
        {"role_code": "complex_manager"},
        format="json",
    )
    assert r.status_code == 201
    assert target.user_roles.filter(role__code="complex_manager").exists()


def test_assign_invalid_role_rejected(make_user, auth_client, rbac, superuser):
    target = make_user(mobile="09120000005")
    r = auth_client(superuser).post(
        f"/api/v1/admin/users/{target.id}/roles",
        {"role_code": "does_not_exist"},
        format="json",
    )
    assert r.status_code == 400


def test_permissions_list_superadmin_only(make_user, auth_client, rbac, assign_role, superuser):
    u = make_user(mobile="09120000004")
    assign_role(u, "employee")
    assert auth_client(u).get("/api/v1/permissions").status_code == 403
    assert auth_client(superuser).get("/api/v1/permissions").status_code == 200

import pytest

pytestmark = pytest.mark.django_db


def test_me_roles_flattens_permissions(make_user, make_role, grant_role, auth):
    u = make_user()
    make_role("complex_manager", permissions=["accommodation.reservation.manage", "accommodation.checkin.manage"])
    grant_role(u, "complex_manager")
    r = auth(u).get("/api/v1/me/roles")
    assert r.status_code == 200
    assert "accommodation.reservation.manage" in r.data["permissions"]
    assert any(role["code"] == "complex_manager" for role in r.data["roles"])
    assert r.data["is_super_admin"] is False


def test_permissions_list_forbidden_for_normal(make_user, make_permission, auth):
    make_permission("x.y.z")
    assert auth(make_user()).get("/api/v1/permissions").status_code == 403


def test_permissions_list_ok_for_super_admin(superuser, make_permission, auth):
    make_permission("x.y.z")
    r = auth(superuser).get("/api/v1/permissions")
    assert r.status_code == 200


def test_role_create_by_super_admin(superuser, make_permission, auth):
    make_permission("accommodation.complex.view")
    r = auth(superuser).post(
        "/api/v1/roles/",
        {"code": "r1", "name": "نقش ۱", "permissions": ["accommodation.complex.view"]},
        format="json",
    )
    assert r.status_code == 201
    assert r.data["permissions"] == ["accommodation.complex.view"]


def test_scope_is_respected_in_me_roles(make_user, make_role, grant_role, auth):
    u = make_user()
    make_role("province_role", permissions=["hr.personnel.view"])
    grant_role(u, "province_role", scope_org_unit_id=42)
    r = auth(u).get("/api/v1/me/roles")
    scopes = [role["scope_org_unit_id"] for role in r.data["roles"]]
    assert 42 in scopes

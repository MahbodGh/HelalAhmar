"""Tests for the per-role dashboard manifest and stats summary."""
import pytest

pytestmark = pytest.mark.django_db


def test_employee_dashboard_excludes_admin(make_user, auth_client, rbac, assign_role):
    u = make_user(mobile="09120000010")
    assign_role(u, "employee")
    r = auth_client(u).get("/api/v1/me/dashboard")
    assert r.status_code == 200
    keys = {s["key"] for s in r.data["sections"]}
    assert "personal" in keys
    assert "admin" not in keys


def test_superadmin_dashboard_has_admin(auth_client, rbac, superuser):
    r = auth_client(superuser).get("/api/v1/me/dashboard")
    keys = {s["key"] for s in r.data["sections"]}
    assert "admin" in keys


def test_summary_total_users_is_live(auth_client, rbac, superuser):
    r = auth_client(superuser).get("/api/v1/me/dashboard/summary")
    assert r.status_code == 200
    assert r.data["identity.total_users"]["status"] == "ok"
    assert r.data["identity.total_users"]["value"] >= 1

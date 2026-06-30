import pytest

pytestmark = pytest.mark.django_db


def test_employee_sees_limited_menu(seeded_rbac, make_user, grant_role, auth):
    u = make_user()
    grant_role(u, "employee")
    r = auth(u).get("/api/v1/me/dashboards")
    codes = [d["code"] for d in r.data]
    assert "overview" in codes  # public to everyone
    assert "hr_personnel" not in codes  # needs hr.personnel.view


def test_super_admin_sees_full_menu(seeded_rbac, superuser, auth):
    r = auth(superuser).get("/api/v1/me/dashboards")
    codes = [d["code"] for d in r.data]
    assert "hr_personnel" in codes and "role_management" in codes


def test_dashboard_has_personal_section(seeded_rbac, make_user, grant_role, auth):
    u = make_user()
    grant_role(u, "employee")
    r = auth(u).get("/api/v1/me/dashboard")
    assert r.status_code == 200
    keys = [s["key"] for s in r.data["sections"]]
    assert "personal" in keys


def test_summary_returns_real_personnel_count(seeded_rbac, superuser, auth):
    from hr.models import Personnel

    Personnel.objects.create(national_id="0012345679", personnel_no="1", first_name="ا", last_name="ب")
    r = auth(superuser).get("/api/v1/me/dashboard/summary")
    assert r.data["hr.total_personnel"]["status"] == "ok"
    assert r.data["hr.total_personnel"]["value"] == 1


def test_summary_pending_for_unbuilt_module(seeded_rbac, superuser, auth):
    r = auth(superuser).get("/api/v1/me/dashboard/summary")
    # the loan module is not built yet -> its stats are still pending
    assert r.data["loan.pending_requests"]["status"] == "pending"

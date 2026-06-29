"""Tests for accommodation base: permissions, unit status, housekeeping, RLS."""
import pytest

pytestmark = pytest.mark.django_db


def test_complex_permissions(make_user, auth_client, rbac, assign_role, superuser):
    viewer = make_user(mobile="09120000030")
    assign_role(viewer, "province_director")  # has accommodation.complex.view, not manage
    payload = {"name": "مهمانسرا", "code": "CX1"}
    assert auth_client(viewer).get("/api/v1/accommodation/complexes").status_code == 200
    assert auth_client(viewer).post("/api/v1/accommodation/complexes", payload, format="json").status_code == 403
    assert auth_client(superuser).post("/api/v1/accommodation/complexes", payload, format="json").status_code == 201


def test_unit_status_and_housekeeping(auth_client, rbac, superuser):
    from accommodation.models import AccommodationComplex, AccommodationUnit, UnitPlan

    cx = AccommodationComplex.objects.create(name="cx", code="CX2")
    plan = UnitPlan.objects.create(name="سوئیت")
    unit = AccommodationUnit.objects.create(complex=cx, plan=plan, name_or_number="101")

    client = auth_client(superuser)
    r = client.post(f"/api/v1/accommodation/units/{unit.id}/status", {"status": "cleaning"}, format="json")
    assert r.status_code == 200 and r.data["status"] == "cleaning"

    q = client.get("/api/v1/accommodation/housekeeping/queue")
    assert q.status_code == 200
    assert any(x["id"] == unit.id for x in q.data)

    r2 = client.post(f"/api/v1/accommodation/units/{unit.id}/mark-cleaned", {}, format="json")
    assert r2.data["status"] == "active"


def test_complex_rls_scoping(make_user, auth_client, rbac, hr_base, assign_role):
    from accommodation.models import AccommodationComplex
    from hr.models import OrgUnit

    org_a = OrgUnit.objects.get(code="ORG-P08")
    org_b = OrgUnit.objects.get(code="ORG-P27")
    AccommodationComplex.objects.create(name="A", code="CA", org_unit=org_a)
    AccommodationComplex.objects.create(name="B", code="CB", org_unit=org_b)

    u = make_user(mobile="09120000031")
    assign_role(u, "province_accommodation_officer", scope=org_a.id)

    r = auth_client(u).get("/api/v1/accommodation/complexes")
    assert r.status_code == 200
    codes = [c["code"] for c in r.data["results"]]
    assert "CA" in codes and "CB" not in codes


def test_complex_summary_is_live(auth_client, rbac, superuser):
    from accommodation.models import AccommodationComplex

    AccommodationComplex.objects.create(name="X", code="CX9")
    r = auth_client(superuser).get("/api/v1/me/dashboard/summary")
    assert r.data["accommodation.total_complexes"]["status"] == "ok"
    assert r.data["accommodation.total_complexes"]["value"] >= 1

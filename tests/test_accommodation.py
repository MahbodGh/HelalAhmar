import pytest

pytestmark = pytest.mark.django_db

# SimpleRouter(trailing_slash=False) — no trailing slashes anywhere
COMPLEXES = "/api/v1/accommodation/complexes"
UNITS = "/api/v1/accommodation/units"


def _plan():
    from accommodation.models import UnitPlan

    return UnitPlan.objects.create(name="سوئیت")


def test_complex_create_by_super_admin(superuser, auth):
    r = auth(superuser).post(COMPLEXES, {"name": "مهمانسرا", "code": "C1"}, format="json")
    assert r.status_code == 201


def test_complex_list_forbidden_without_permission(make_user, auth):
    assert auth(make_user()).get(COMPLEXES).status_code == 403


def test_unit_status_change_and_housekeeping_flow(superuser, auth):
    from accommodation.models import AccommodationComplex, AccommodationUnit

    cx = AccommodationComplex.objects.create(name="مهمانسرا", code="C1")
    unit = AccommodationUnit.objects.create(
        complex=cx, plan=_plan(), name_or_number="101", standard_capacity=2, max_capacity=4
    )
    c = auth(superuser)

    set_cleaning = c.post(f"{UNITS}/{unit.id}/status", {"status": "cleaning"}, format="json")
    assert set_cleaning.status_code == 200
    assert set_cleaning.data["status"] == "cleaning"

    queue = c.get("/api/v1/accommodation/housekeeping/queue")
    assert queue.status_code == 200
    assert any(u["id"] == unit.id for u in queue.data)

    cleaned = c.post(f"{UNITS}/{unit.id}/mark-cleaned", {}, format="json")
    assert cleaned.status_code == 200
    assert cleaned.data["status"] == "active"


def test_complex_plan_board(superuser, auth):
    from accommodation.models import AccommodationComplex, AccommodationUnit

    cx = AccommodationComplex.objects.create(name="مهمانسرا", code="C1")
    AccommodationUnit.objects.create(complex=cx, plan=_plan(), name_or_number="101")
    r = auth(superuser).get(f"{COMPLEXES}/{cx.id}/plan")
    assert r.status_code == 200
    assert "status_summary" in r.data
    assert r.data["status_summary"].get("active") == 1


def test_complex_list_is_rls_scoped(make_user, make_role, grant_role, auth):
    from accommodation.models import AccommodationComplex
    from hr.models import OrgUnit, Province

    p = Province.objects.create(name="A", code="PA")
    hq = OrgUnit.objects.create(name="HQ", code="HQ", type="hq")
    org_a = OrgUnit.objects.create(name="A", code="OA", type="province_org", parent=hq, province=p)
    org_b = OrgUnit.objects.create(name="B", code="OB", type="province_org", parent=hq)
    AccommodationComplex.objects.create(name="A", code="CA", org_unit=org_a)
    AccommodationComplex.objects.create(name="B", code="CB", org_unit=org_b)

    make_role("acc_view", permissions=["accommodation.complex.view"])
    u = make_user()
    grant_role(u, "acc_view", scope_org_unit_id=org_a.id)

    r = auth(u).get(COMPLEXES)
    codes = [x["code"] for x in r.data["results"]]
    assert codes == ["CA"]

import pytest
from datetime import date, timedelta

pytestmark = pytest.mark.django_db

BI = "/api/v1/accommodation/bi"


def _complex(code="C1", province=None, org_unit=None):
    from accommodation.models import AccommodationComplex

    return AccommodationComplex.objects.create(name=code, code=code, province=province, org_unit=org_unit)


def _unit(cx, num="101"):
    from accommodation.models import AccommodationUnit, UnitPlan

    plan, _ = UnitPlan.objects.get_or_create(name="سوئیت")
    return AccommodationUnit.objects.create(
        complex=cx, plan=plan, name_or_number=num, standard_capacity=4, max_capacity=4
    )


def _person(nid="0012345679"):
    from hr.models import Personnel

    return Personnel.objects.create(national_id=nid, personnel_no=nid[-2:], first_name="ا", last_name="ب")


def _reservation(unit, person, status="confirmed", ci=None, co=None):
    from accommodation.models import Reservation

    ci = ci or date.today()
    co = co or (ci + timedelta(days=2))
    r = Reservation.objects.create(
        unit=unit, personnel=person, check_in_date=ci, check_out_date=co,
        nights=(co - ci).days, status=status, total_cost=0,
    )
    r.code = f"RSV-{r.id:06d}"
    r.save(update_fields=["code"])
    return r


def test_bi_requires_permission(make_user, auth):
    assert auth(make_user()).get(f"{BI}/summary").status_code == 403


def test_bi_summary_for_super_admin(superuser, auth):
    cx = _complex()
    u = _unit(cx)
    _reservation(u, _person())
    r = auth(superuser).get(f"{BI}/summary")
    assert r.status_code == 200
    assert r.data["total_complexes"] >= 1
    assert r.data["active_reservations"] >= 1
    assert "occupancy_rate" in r.data


def test_bi_trend_returns_list(superuser, auth):
    cx = _complex()
    u = _unit(cx)
    _reservation(u, _person())
    r = auth(superuser).get(f"{BI}/reservation-trend?months=6")
    assert r.status_code == 200
    assert isinstance(r.data, list)


def test_bi_status_breakdown_shape(superuser, auth):
    cx = _complex()
    _unit(cx)
    r = auth(superuser).get(f"{BI}/status-breakdown")
    assert r.status_code == 200
    assert "units" in r.data and "reservations" in r.data


def test_bi_is_rls_scoped(make_user, make_role, grant_role, auth):
    from hr.models import OrgUnit, Province

    pa = Province.objects.create(name="استان‌الف", code="PA")
    pb = Province.objects.create(name="استان‌ب", code="PB")
    hq = OrgUnit.objects.create(name="HQ", code="HQ", type="hq")
    oa = OrgUnit.objects.create(name="A", code="OA", type="province_org", parent=hq, province=pa)
    ob = OrgUnit.objects.create(name="B", code="OB", type="province_org", parent=hq, province=pb)

    ca = _complex("CA", province=pa, org_unit=oa)
    cb = _complex("CB", province=pb, org_unit=ob)
    _reservation(_unit(ca, "101"), _person("0012345679"))
    _reservation(_unit(cb, "201"), _person("1234567891"))

    make_role("bi", permissions=["accommodation.bi.view"])
    user = make_user()
    grant_role(user, "bi", scope_org_unit_id=oa.id)

    r = auth(user).get(f"{BI}/occupancy-by-province")
    assert r.status_code == 200
    names = [row["province_name"] for row in r.data]
    assert "استان‌الف" in names and "استان‌ب" not in names  # only own province

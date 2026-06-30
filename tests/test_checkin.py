import pytest
from datetime import date, timedelta

from django.utils import timezone

pytestmark = pytest.mark.django_db

RES = "/api/v1/accommodation/reservations"


def _setup(make_user, make_role, grant_role, paid=True):
    from accommodation.application import services as app
    from accommodation.models import (
        AccommodationComplex,
        AccommodationUnit,
        ReservationPeriod,
        UnitPlan,
    )
    from hr.models import Personnel

    cx = AccommodationComplex.objects.create(name="مهمانسرا", code="C1")
    plan = UnitPlan.objects.create(name="سوئیت")
    unit = AccommodationUnit.objects.create(
        complex=cx, plan=plan, name_or_number="101", standard_capacity=4, max_capacity=4
    )
    now = timezone.now()
    p = ReservationPeriod.objects.create(
        title="دوره", method="fcfs", status="active",
        enroll_start=now - timedelta(days=1), enroll_end=now + timedelta(days=10),
        stay_from=date.today(), stay_to=date.today() + timedelta(days=30),
        min_nights=1, max_nights=7, price_personnel=100000,
    )
    p.units.add(unit)
    person = Personnel.objects.create(national_id="0012345679", personnel_no="1", first_name="ا", last_name="ب")
    u = make_user(mobile="09120012345")
    u.personnel_id = person.id
    u.save(update_fields=["personnel_id"])
    make_role("emp", permissions=["accommodation.reservation.create"])
    grant_role(u, "emp")

    res = app.create_reservation(
        user=u, period=p, unit=unit, check_in=date.today(), check_out=date.today() + timedelta(days=2)
    )
    if paid:
        app.pay_reservation(res)
    return u, res, unit


def test_voucher_issued_on_pay_and_fetchable(make_user, make_role, grant_role, auth):
    from accommodation.models import Voucher

    u, res, _ = _setup(make_user, make_role, grant_role, paid=True)
    assert Voucher.objects.filter(reservation=res).exists()
    r = auth(u).get(f"{RES}/{res.id}/voucher")
    assert r.status_code == 200
    assert r.data["token"]
    assert r.data["qr_payload"].startswith("HELAL-RSV:")


def test_verify_voucher_by_token(superuser, make_user, make_role, grant_role, auth):
    from accommodation.models import Voucher

    _, res, _ = _setup(make_user, make_role, grant_role, paid=True)
    token = Voucher.objects.get(reservation=res).token
    c = auth(superuser)
    ok = c.post(f"{RES}/verify-voucher", {"token": token}, format="json")
    assert ok.status_code == 200 and ok.data["code"] == res.code
    bad = c.post(f"{RES}/verify-voucher", {"token": "invalid-token"}, format="json")
    assert bad.status_code == 404


def test_check_in_out_cycle_feeds_housekeeping(superuser, make_user, make_role, grant_role, auth):
    _, res, unit = _setup(make_user, make_role, grant_role, paid=True)
    c = auth(superuser)

    ci = c.post(f"{RES}/{res.id}/check-in", {}, format="json")
    assert ci.status_code == 200 and ci.data["status"] == "checked_in"

    co = c.post(f"{RES}/{res.id}/check-out", {}, format="json")
    assert co.status_code == 200 and co.data["status"] == "checked_out"

    unit.refresh_from_db()
    assert unit.status == "cleaning"  # check-out pushes the unit to housekeeping

    q = c.get("/api/v1/accommodation/housekeeping/queue")
    assert any(x["id"] == unit.id for x in q.data)


def test_check_in_requires_confirmed(superuser, make_user, make_role, grant_role, auth):
    _, res, _ = _setup(make_user, make_role, grant_role, paid=False)  # still pending_payment
    r = auth(superuser).post(f"{RES}/{res.id}/check-in", {}, format="json")
    assert r.status_code == 400


def test_employee_cannot_check_in(make_user, make_role, grant_role, auth):
    u, res, _ = _setup(make_user, make_role, grant_role, paid=True)
    r = auth(u).post(f"{RES}/{res.id}/check-in", {}, format="json")
    assert r.status_code == 403  # employee lacks accommodation.checkin.manage

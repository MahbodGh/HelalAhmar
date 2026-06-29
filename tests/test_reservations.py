import pytest
from datetime import date, timedelta

from django.utils import timezone

pytestmark = pytest.mark.django_db

PERIODS = "/api/v1/accommodation/periods"
RESERVATIONS = "/api/v1/accommodation/reservations"


def _complex_unit():
    from accommodation.models import AccommodationComplex, AccommodationUnit, UnitPlan

    cx = AccommodationComplex.objects.create(name="مهمانسرا", code="C1")
    plan = UnitPlan.objects.create(name="سوئیت")
    unit = AccommodationUnit.objects.create(
        complex=cx, plan=plan, name_or_number="101", standard_capacity=4, max_capacity=4
    )
    return cx, unit


def _active_period(unit, **overrides):
    from accommodation.models import ReservationPeriod

    now = timezone.now()
    defaults = dict(
        title="نوروز",
        method="fcfs",
        status="active",
        enroll_start=now - timedelta(days=1),
        enroll_end=now + timedelta(days=10),
        stay_from=date.today(),
        stay_to=date.today() + timedelta(days=30),
        min_nights=1,
        max_nights=7,
        max_total_companions=3,
        price_personnel=100000,
        price_first_degree_companion=50000,
        price_other_companion=70000,
        payment_deadline_hours=24,
    )
    defaults.update(overrides)
    p = ReservationPeriod.objects.create(**defaults)
    p.units.add(unit)
    return p


def _linked_user(make_user, national_id="0012345679", **kw):
    from hr.models import Personnel

    person = Personnel.objects.create(
        national_id=national_id, personnel_no=national_id[-3:], first_name="ا", last_name="ب", **kw
    )
    u = make_user(mobile="0912" + national_id[:7])
    u.personnel_id = person.id
    u.save(update_fields=["personnel_id"])
    return u, person


# --- periods --------------------------------------------------------------- #
def test_period_create_requires_manage(make_user, auth):
    body = {
        "title": "x", "method": "fcfs", "status": "active",
        "enroll_start": "2026-01-01T00:00:00Z", "enroll_end": "2026-12-01T00:00:00Z",
        "stay_from": "2026-01-01", "stay_to": "2026-12-01",
    }
    assert auth(make_user()).post(PERIODS, body, format="json").status_code == 403


def test_active_periods_lists_open(superuser, auth):
    _, unit = _complex_unit()
    _active_period(unit)
    r = auth(superuser).get(f"{PERIODS}/active")
    assert r.status_code == 200
    assert len(r.data) == 1


def test_available_units(superuser, auth):
    _, unit = _complex_unit()
    p = _active_period(unit)
    ci = date.today()
    co = ci + timedelta(days=2)
    r = auth(superuser).get(f"{PERIODS}/{p.id}/available-units?check_in={ci}&check_out={co}&persons=2")
    assert r.status_code == 200
    assert any(u["id"] == unit.id for u in r.data)


# --- reservations ---------------------------------------------------------- #
def test_create_reservation_success_and_cost(make_user, make_role, grant_role, auth):
    _, unit = _complex_unit()
    p = _active_period(unit)
    u, person = _linked_user(make_user)
    make_role("emp", permissions=["accommodation.reservation.create"])
    grant_role(u, "emp")
    ci = date.today()
    co = ci + timedelta(days=2)
    r = auth(u).post(
        RESERVATIONS,
        {"period": p.id, "unit": unit.id, "check_in_date": str(ci), "check_out_date": str(co),
         "first_degree_companions": 1, "other_companions": 0},
        format="json",
    )
    assert r.status_code == 201
    assert r.data["status"] == "pending_payment"
    # 2 nights * (100000 personnel + 1*50000 first-degree) = 300000
    assert r.data["total_cost"] == 300000
    assert r.data["code"].startswith("RSV-")


def test_overlapping_reservation_conflicts(make_user, make_role, grant_role, auth):
    from accommodation.application import services as app

    _, unit = _complex_unit()
    p = _active_period(unit)
    u, person = _linked_user(make_user)
    make_role("emp", permissions=["accommodation.reservation.create"])
    grant_role(u, "emp")
    ci = date.today()
    co = ci + timedelta(days=3)

    first = app.create_reservation(user=u, period=p, unit=unit, check_in=ci, check_out=co)
    app.pay_reservation(first)  # confirmed -> holds the unit

    r = auth(u).post(
        RESERVATIONS,
        {"period": p.id, "unit": unit.id, "check_in_date": str(ci + timedelta(days=1)),
         "check_out_date": str(ci + timedelta(days=2))},
        format="json",
    )
    assert r.status_code == 409


def test_capacity_exceeded_rejected(make_user, make_role, grant_role, auth):
    _, unit = _complex_unit()  # capacity 4
    p = _active_period(unit, allowed_capacity_increase=0, max_total_companions=10)
    u, person = _linked_user(make_user)
    make_role("emp", permissions=["accommodation.reservation.create"])
    grant_role(u, "emp")
    ci = date.today()
    co = ci + timedelta(days=1)
    r = auth(u).post(
        RESERVATIONS,
        {"period": p.id, "unit": unit.id, "check_in_date": str(ci), "check_out_date": str(co),
         "first_degree_companions": 4, "other_companions": 0},  # 1 + 4 = 5 > capacity 4
        format="json",
    )
    assert r.status_code == 400


def test_outside_stay_window_rejected(make_user, make_role, grant_role, auth):
    _, unit = _complex_unit()
    p = _active_period(unit, stay_from=date.today(), stay_to=date.today() + timedelta(days=2))
    u, person = _linked_user(make_user)
    make_role("emp", permissions=["accommodation.reservation.create"])
    grant_role(u, "emp")
    ci = date.today() + timedelta(days=10)  # outside window
    co = ci + timedelta(days=1)
    r = auth(u).post(
        RESERVATIONS,
        {"period": p.id, "unit": unit.id, "check_in_date": str(ci), "check_out_date": str(co)},
        format="json",
    )
    assert r.status_code == 400


def test_pay_and_cancel_flow(make_user, make_role, grant_role, auth):
    from accommodation.application import services as app

    _, unit = _complex_unit()
    p = _active_period(unit)
    u, person = _linked_user(make_user)
    make_role("emp", permissions=["accommodation.reservation.create"])
    grant_role(u, "emp")
    res = app.create_reservation(user=u, period=p, unit=unit, check_in=date.today(), check_out=date.today() + timedelta(days=1))

    c = auth(u)
    paid = c.post(f"{RESERVATIONS}/{res.id}/pay", {}, format="json")
    assert paid.status_code == 200 and paid.data["status"] == "confirmed"

    cancelled = c.post(f"{RESERVATIONS}/{res.id}/cancel", {}, format="json")
    assert cancelled.status_code == 200 and cancelled.data["status"] == "cancelled"
    assert cancelled.data["is_refunded"] is True


def test_employee_sees_only_own_reservations(make_user, make_role, grant_role, auth):
    from accommodation.application import services as app

    _, unit = _complex_unit()
    p = _active_period(unit)
    make_role("emp", permissions=["accommodation.reservation.create"])

    u1, _ = _linked_user(make_user, national_id="0012345679")
    u2, _ = _linked_user(make_user, national_id="1234567891")
    grant_role(u1, "emp")
    grant_role(u2, "emp")
    app.create_reservation(user=u1, period=p, unit=unit, check_in=date.today(), check_out=date.today() + timedelta(days=1))

    r = auth(u2).get(RESERVATIONS)
    assert r.data["count"] == 0  # u2 sees none of u1's reservations

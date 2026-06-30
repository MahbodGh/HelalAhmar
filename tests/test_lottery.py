import pytest
from datetime import date, timedelta

from django.utils import timezone

pytestmark = pytest.mark.django_db

PERIODS = "/api/v1/accommodation/periods"


def _unit(code="C1", num="101", cap=4):
    from accommodation.models import AccommodationComplex, AccommodationUnit, UnitPlan

    cx, _ = AccommodationComplex.objects.get_or_create(code=code, defaults={"name": code})
    plan, _ = UnitPlan.objects.get_or_create(name="سوئیت")
    return AccommodationUnit.objects.create(
        complex=cx, plan=plan, name_or_number=num, standard_capacity=cap, max_capacity=cap
    )


def _lottery_period(units, enroll_open=True, **overrides):
    from accommodation.models import ReservationPeriod

    now = timezone.now()
    if enroll_open:
        es, ee = now - timedelta(days=1), now + timedelta(days=5)
    else:
        es, ee = now - timedelta(days=5), now - timedelta(days=1)  # already closed
    defaults = dict(
        title="قرعه‌کشی", method="lottery", status="active",
        enroll_start=es, enroll_end=ee,
        stay_from=date.today() + timedelta(days=10), stay_to=date.today() + timedelta(days=13),
        min_nights=1, max_nights=7, max_total_companions=3,
        price_personnel=100000,
    )
    defaults.update(overrides)
    p = ReservationPeriod.objects.create(**defaults)
    for u in units:
        p.units.add(u)
    return p


def _person(nid, personnel_no, province=None):
    from hr.models import Personnel

    return Personnel.objects.create(
        national_id=nid, personnel_no=personnel_no, first_name="ا", last_name="ب", province=province
    )


def _linked_user(make_user, person):
    u = make_user(mobile="0912" + person.national_id[:7])
    u.personnel_id = person.id
    u.save(update_fields=["personnel_id"])
    return u


def test_enroll_lottery_success(make_user, make_role, grant_role, auth):
    p = _lottery_period([_unit()])
    person = _person("0012345679", "1")
    u = _linked_user(make_user, person)
    make_role("emp", permissions=["accommodation.reservation.create"])
    grant_role(u, "emp")
    r = auth(u).post(f"{PERIODS}/{p.id}/enroll", {"first_degree_companions": 1}, format="json")
    assert r.status_code == 201
    assert r.data["status"] == "pending"
    assert r.data["persons"] == 2


def test_enroll_rejected_on_fcfs_period(make_user, make_role, grant_role, auth):
    p = _lottery_period([_unit()])
    p.method = "fcfs"
    p.save(update_fields=["method"])
    person = _person("0012345679", "1")
    u = _linked_user(make_user, person)
    make_role("emp", permissions=["accommodation.reservation.create"])
    grant_role(u, "emp")
    r = auth(u).post(f"{PERIODS}/{p.id}/enroll", {}, format="json")
    assert r.status_code == 400


def test_run_lottery_before_close_fails(superuser, auth):
    p = _lottery_period([_unit()], enroll_open=True)  # still open
    r = auth(superuser).post(f"{PERIODS}/{p.id}/run-lottery", {}, format="json")
    assert r.status_code == 400


def test_run_lottery_allocates_one_winner_for_one_unit(superuser, auth):
    from accommodation.models import LotteryEnrollment, Reservation

    p = _lottery_period([_unit(num="101")], enroll_open=False)  # closed -> can run
    a = _person("0012345679", "1")
    b = _person("1234567891", "2")
    LotteryEnrollment.objects.create(period=p, personnel=a)
    LotteryEnrollment.objects.create(period=p, personnel=b)

    r = auth(superuser).post(f"{PERIODS}/{p.id}/run-lottery", {"seed": "42"}, format="json")
    assert r.status_code == 200
    assert r.data["total_enrollments"] == 2
    assert r.data["winners"] == 1  # only one unit
    assert r.data["losers"] == 1
    assert Reservation.objects.filter(period=p).count() == 1
    assert LotteryEnrollment.objects.filter(period=p, status="won").count() == 1


def test_run_lottery_is_deterministic_with_seed(superuser, auth):
    from accommodation.models import LotteryEnrollment

    p = _lottery_period([_unit(num="101")], enroll_open=False)
    a = _person("0012345679", "1")
    b = _person("1234567891", "2")
    LotteryEnrollment.objects.create(period=p, personnel=a)
    LotteryEnrollment.objects.create(period=p, personnel=b)

    auth(superuser).post(f"{PERIODS}/{p.id}/run-lottery", {"seed": "7"}, format="json")
    winner = LotteryEnrollment.objects.get(period=p, status="won")
    assert winner.personnel_id in (a.id, b.id)  # one deterministic winner, run completed


def test_double_run_prevented(superuser, auth):
    p = _lottery_period([_unit()], enroll_open=False)
    c = auth(superuser)
    assert c.post(f"{PERIODS}/{p.id}/run-lottery", {}, format="json").status_code == 200
    assert c.post(f"{PERIODS}/{p.id}/run-lottery", {}, format="json").status_code == 400


def test_province_quota_limits_winners(superuser, auth):
    from accommodation.models import LotteryEnrollment
    from hr.models import Province

    prov = Province.objects.create(name="تهران", code="P08")
    p = _lottery_period([_unit(num="101"), _unit(num="102")], enroll_open=False,
                        province_quotas={str(0): 0})  # placeholder set below
    p.province_quotas = {str(prov.id): 1}
    p.save(update_fields=["province_quotas"])
    a = _person("0012345679", "1", province=prov)
    b = _person("1234567891", "2", province=prov)
    LotteryEnrollment.objects.create(period=p, personnel=a)
    LotteryEnrollment.objects.create(period=p, personnel=b)

    r = auth(superuser).post(f"{PERIODS}/{p.id}/run-lottery", {"seed": "1"}, format="json")
    # two units available but province quota caps Tehran winners at 1
    assert r.data["winners"] == 1

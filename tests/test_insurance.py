import pytest
from datetime import date

pytestmark = pytest.mark.django_db

PLANS = "/api/v1/insurance/plans"
REQUESTS = "/api/v1/insurance/requests"


def _plan(code="PLAN-BASE", premium=1000000, allow_dependents=True, max_dependents=6):
    from insurance.models import InsurancePlan

    return InsurancePlan.objects.create(
        name=code, code=code, premium_per_person=premium,
        allow_dependents=allow_dependents, max_dependents=max_dependents, is_active=True,
    )


def _person(nid="0012345679", org_unit=None):
    from hr.models import Personnel

    return Personnel.objects.create(
        national_id=nid, personnel_no=nid[-2:], first_name="ا", last_name="ب",
        org_unit=org_unit, birth_date=date(1990, 1, 1),
    )


def _linked(make_user, person):
    u = make_user(mobile="0912" + person.national_id[:7])
    u.personnel_id = person.id
    u.save(update_fields=["personnel_id"])
    return u


def _dependent(person, nid, birth=date(2010, 1, 1)):
    from hr.models import Dependent

    return Dependent.objects.create(
        personnel=person, relation="child", first_name="ف", last_name="ب",
        national_id=nid, birth_date=birth,
    )


# --- plans ----------------------------------------------------------------- #
def test_plan_create_requires_manage(make_user, auth):
    body = {"name": "x", "code": "X1", "premium_per_person": 1000}
    assert auth(make_user()).post(PLANS, body, format="json").status_code == 403


def test_plan_create_by_expert(make_user, make_role, grant_role, auth):
    make_role("ins", permissions=["insurance.request.manage"])
    u = make_user()
    grant_role(u, "ins")
    r = auth(u).post(PLANS, {"name": "طرح", "code": "X1", "premium_per_person": 1000}, format="json")
    assert r.status_code == 201


def test_plan_list_visible_to_employee(make_user, auth):
    _plan()
    r = auth(make_user()).get(f"{PLANS}?active=1")
    assert r.status_code == 200 and r.data["count"] == 1


# --- requests -------------------------------------------------------------- #
def test_create_request_computes_premium(make_user, auth):
    plan = _plan(premium=1000000)
    person = _person()
    u = _linked(make_user, person)
    d1 = _dependent(person, "1111111111")
    d2 = _dependent(person, "2222222222")
    r = auth(u).post(
        REQUESTS, {"plan": plan.id, "dependent_ids": [d1.id, d2.id]}, format="json"
    )
    assert r.status_code == 201
    assert r.data["status"] == "submitted"
    assert r.data["insured_count"] == 3              # self + 2 dependents
    assert r.data["premium_total"] == 3000000        # 1,000,000 * 3
    assert r.data["code"].startswith("INS-")


def test_request_rejects_foreign_dependent(make_user, auth):
    plan = _plan()
    person = _person("0012345679")
    other = _person("1234567891")
    u = _linked(make_user, person)
    foreign = _dependent(other, "3333333333")
    r = auth(u).post(REQUESTS, {"plan": plan.id, "dependent_ids": [foreign.id]}, format="json")
    assert r.status_code == 400


def test_employee_sees_only_own_requests(make_user, make_role, grant_role, auth):
    from insurance.application import services as app

    plan = _plan()
    p1 = _person("0012345679")
    p2 = _person("1234567891")
    u1 = _linked(make_user, p1)
    u2 = _linked(make_user, p2)
    app.create_request(user=u1, plan=plan)

    r = auth(u2).get(REQUESTS)
    assert r.data["count"] == 0


def test_expert_approve_flow(make_user, make_role, grant_role, auth):
    from insurance.application import services as app

    plan = _plan()
    person = _person()
    emp = _linked(make_user, person)
    req = app.create_request(user=emp, plan=plan)

    make_role("ins", permissions=["insurance.request.manage"])
    expert = make_user(mobile="09129999999")
    grant_role(expert, "ins")

    r = auth(expert).post(f"{REQUESTS}/{req.id}/approve", {"note": "تأیید شد"}, format="json")
    assert r.status_code == 200 and r.data["status"] == "approved"
    assert r.data["review_note"] == "تأیید شد"


def test_employee_cannot_approve(make_user, auth):
    from insurance.application import services as app

    plan = _plan()
    person = _person()
    emp = _linked(make_user, person)
    req = app.create_request(user=emp, plan=plan)
    r = auth(emp).post(f"{REQUESTS}/{req.id}/approve", {}, format="json")
    assert r.status_code == 403


def test_pending_requests_stat_is_real(make_user, make_role, grant_role, superuser, auth):
    from insurance.application import services as app

    plan = _plan()
    person = _person()
    emp = _linked(make_user, person)
    app.create_request(user=emp, plan=plan)

    r = auth(superuser).get("/api/v1/me/dashboard/summary")
    assert r.data["insurance.pending_requests"]["status"] == "ok"
    assert r.data["insurance.pending_requests"]["value"] >= 1


def test_request_rls_scoped_for_expert(make_user, make_role, grant_role, auth):
    from hr.models import OrgUnit, Province
    from insurance.application import services as app

    pa = Province.objects.create(name="الف", code="PA")
    hq = OrgUnit.objects.create(name="HQ", code="HQ", type="hq")
    oa = OrgUnit.objects.create(name="A", code="OA", type="province_org", parent=hq, province=pa)
    ob = OrgUnit.objects.create(name="B", code="OB", type="province_org", parent=hq)

    plan = _plan()
    pin = _person("0012345679", org_unit=oa)
    pout = _person("1234567891", org_unit=ob)
    app.create_request(user=_linked(make_user, pin), plan=plan)
    app.create_request(user=_linked(make_user, pout), plan=plan)

    make_role("ins", permissions=["insurance.request.manage"])
    expert = make_user(mobile="09128888888")
    grant_role(expert, "ins", scope_org_unit_id=oa.id)

    r = auth(expert).get(REQUESTS)
    nids = [row["personnel"] for row in r.data["results"]]
    assert pin.id in nids and pout.id not in nids

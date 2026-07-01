import pytest
from datetime import date

pytestmark = pytest.mark.django_db

CLAIMS = "/api/v1/insurance/claims"


def _plan(code="PLAN", ceiling=100_000_000, premium=1_000_000):
    from insurance.models import InsurancePlan

    return InsurancePlan.objects.create(
        name=code, code=code, premium_per_person=premium,
        coverage_ceiling=ceiling, is_active=True, max_dependents=6,
    )


def _person(nid="0012345679", org_unit=None):
    from hr.models import Personnel

    return Personnel.objects.create(
        national_id=nid, personnel_no=nid[-2:], first_name="ا", last_name="ب",
        org_unit=org_unit, birth_date=date(1990, 1, 1),
    )


def _linked(make_user, person, mobile=None):
    u = make_user(mobile=mobile or ("0912" + person.national_id[:7]))
    u.personnel_id = person.id
    u.save(update_fields=["personnel_id"])
    return u


def _dependent(person, nid):
    from hr.models import Dependent

    return Dependent.objects.create(
        personnel=person, relation="child", first_name="ف", last_name="ب",
        national_id=nid, birth_date=date(2012, 1, 1),
    )


def _approved(make_user, ceiling=100_000_000, nid="0012345679", org_unit=None, mobile=None):
    from insurance.application import services as app

    plan = _plan(code=f"PLAN-{nid}", ceiling=ceiling)
    person = _person(nid, org_unit=org_unit)
    emp = _linked(make_user, person, mobile=mobile)
    req = app.create_request(user=emp, plan=plan)
    app.approve_request(req, emp)
    return plan, person, emp, req


def _expert(make_user, make_role, grant_role, mobile="09129999999", scope=None):
    make_role("ins", permissions=["insurance.request.manage"])
    e = make_user(mobile=mobile)
    grant_role(e, "ins", scope_org_unit_id=scope)
    return e


def test_create_claim_against_approved_policy(make_user, auth):
    _, _, emp, req = _approved(make_user)
    r = auth(emp).post(
        CLAIMS, {"request": req.id, "service_type": "بستری", "claimed_amount": 5_000_000}, format="json"
    )
    assert r.status_code == 201
    assert r.data["status"] == "submitted"
    assert r.data["code"].startswith("CLM-")


def test_claim_requires_approved_policy(make_user, auth):
    from insurance.application import services as app

    plan = _plan()
    person = _person()
    emp = _linked(make_user, person)
    req = app.create_request(user=emp, plan=plan)  # still submitted, not approved
    r = auth(emp).post(CLAIMS, {"request": req.id, "service_type": "x", "claimed_amount": 1000}, format="json")
    assert r.status_code == 400


def test_claim_foreign_patient_rejected(make_user, auth):
    _, person, emp, req = _approved(make_user)  # policy has no insured dependents
    dep = _dependent(person, "4444444444")
    r = auth(emp).post(
        CLAIMS,
        {"request": req.id, "service_type": "x", "claimed_amount": 1000, "patient_dependent_id": dep.id},
        format="json",
    )
    assert r.status_code == 400


def test_approve_claim_within_ceiling(make_user, make_role, grant_role, auth):
    from insurance.application import services as app

    _, _, emp, req = _approved(make_user, ceiling=10_000_000)
    claim = app.create_claim(user=emp, request=req, service_type="بستری", claimed_amount=6_000_000)
    expert = _expert(make_user, make_role, grant_role)
    r = auth(expert).post(f"{CLAIMS}/{claim.id}/approve", {"approved_amount": 5_000_000}, format="json")
    assert r.status_code == 200
    assert r.data["status"] == "approved"
    assert r.data["approved_amount"] == 5_000_000


def test_approve_exceeding_claimed_rejected(make_user, make_role, grant_role, auth):
    from insurance.application import services as app

    _, _, emp, req = _approved(make_user)
    claim = app.create_claim(user=emp, request=req, service_type="x", claimed_amount=1_000_000)
    expert = _expert(make_user, make_role, grant_role)
    r = auth(expert).post(f"{CLAIMS}/{claim.id}/approve", {"approved_amount": 2_000_000}, format="json")
    assert r.status_code == 400  # approved > claimed


def test_ceiling_is_cumulative(make_user, make_role, grant_role, auth):
    from insurance.application import services as app

    _, _, emp, req = _approved(make_user, ceiling=10_000_000)
    expert = _expert(make_user, make_role, grant_role)

    c1 = app.create_claim(user=emp, request=req, service_type="x", claimed_amount=7_000_000)
    ok = auth(expert).post(f"{CLAIMS}/{c1.id}/approve", {"approved_amount": 7_000_000}, format="json")
    assert ok.status_code == 200

    c2 = app.create_claim(user=emp, request=req, service_type="y", claimed_amount=6_000_000)
    over = auth(expert).post(f"{CLAIMS}/{c2.id}/approve", {"approved_amount": 6_000_000}, format="json")
    assert over.status_code == 400  # only 3,000,000 of the ceiling remains


def test_employee_cannot_approve_claim(make_user, auth):
    from insurance.application import services as app

    _, _, emp, req = _approved(make_user)
    claim = app.create_claim(user=emp, request=req, service_type="x", claimed_amount=1000)
    r = auth(emp).post(f"{CLAIMS}/{claim.id}/approve", {"approved_amount": 1000}, format="json")
    assert r.status_code == 403


def test_mark_paid_flow(make_user, make_role, grant_role, auth):
    from insurance.application import services as app

    _, _, emp, req = _approved(make_user)
    claim = app.create_claim(user=emp, request=req, service_type="x", claimed_amount=1_000_000)
    expert = _expert(make_user, make_role, grant_role)
    auth(expert).post(f"{CLAIMS}/{claim.id}/approve", {"approved_amount": 1_000_000}, format="json")
    paid = auth(expert).post(f"{CLAIMS}/{claim.id}/mark-paid", {}, format="json")
    assert paid.status_code == 200 and paid.data["status"] == "paid"


def test_claim_rls_scoped_for_expert(make_user, make_role, grant_role, auth):
    from hr.models import OrgUnit, Province
    from insurance.application import services as app

    pa = Province.objects.create(name="الف", code="PA")
    hq = OrgUnit.objects.create(name="HQ", code="HQ", type="hq")
    oa = OrgUnit.objects.create(name="A", code="OA", type="province_org", parent=hq, province=pa)
    ob = OrgUnit.objects.create(name="B", code="OB", type="province_org", parent=hq)

    _, pin, emp_in, req_in = _approved(make_user, nid="0012345679", org_unit=oa, mobile="09120000001")
    _, pout, emp_out, req_out = _approved(make_user, nid="1234567891", org_unit=ob, mobile="09120000002")
    app.create_claim(user=emp_in, request=req_in, service_type="x", claimed_amount=1000)
    app.create_claim(user=emp_out, request=req_out, service_type="x", claimed_amount=1000)

    expert = _expert(make_user, make_role, grant_role, mobile="09128888888", scope=oa.id)
    r = auth(expert).get(CLAIMS)
    persons = [row["personnel"] for row in r.data["results"]]
    assert pin.id in persons and pout.id not in persons

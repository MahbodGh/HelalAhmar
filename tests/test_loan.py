import pytest
from datetime import date

pytestmark = pytest.mark.django_db

TYPES = "/api/v1/loan/types"
REQUESTS = "/api/v1/loan/requests"


def _type(code="GHARZ", max_amount=100_000_000, max_installments=24, profit=0, budget=0, block=True):
    from loan.models import LoanType

    return LoanType.objects.create(
        name=code, code=code, max_amount=max_amount, max_installments=max_installments,
        profit_rate=profit, fund_budget=budget, block_if_active_loan=block, is_active=True,
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


def _expert(make_user, make_role, grant_role, mobile="09129999999", scope=None):
    make_role("ln", permissions=["loan.request.manage"])
    e = make_user(mobile=mobile)
    grant_role(e, "ln", scope_org_unit_id=scope)
    return e


# --- types ----------------------------------------------------------------- #
def test_type_create_requires_manage(make_user, auth):
    body = {"name": "x", "code": "X1", "max_amount": 1000, "max_installments": 12}
    assert auth(make_user()).post(TYPES, body, format="json").status_code == 403


def test_type_list_visible_to_employee(make_user, auth):
    _type()
    r = auth(make_user()).get(f"{TYPES}?active=1")
    assert r.status_code == 200 and r.data["count"] == 1


# --- requests -------------------------------------------------------------- #
def test_create_request_computes_installment(make_user, auth):
    lt = _type(max_amount=120_000_000, max_installments=24, profit=0)
    person = _person()
    u = _linked(make_user, person)
    r = auth(u).post(
        REQUESTS, {"loan_type": lt.id, "requested_amount": 120_000_000, "installments_count": 24}, format="json"
    )
    assert r.status_code == 201
    assert r.data["status"] == "submitted"
    assert r.data["monthly_installment"] == 5_000_000    # 120,000,000 / 24, gharz (0%)
    assert r.data["code"].startswith("LN-")


def test_request_exceeding_max_amount_rejected(make_user, auth):
    lt = _type(max_amount=50_000_000)
    u = _linked(make_user, _person())
    r = auth(u).post(REQUESTS, {"loan_type": lt.id, "requested_amount": 90_000_000, "installments_count": 12}, format="json")
    assert r.status_code == 400


def test_block_second_active_loan(make_user, auth):
    from loan.application import services as app

    lt = _type(block=True)
    person = _person()
    u = _linked(make_user, person)
    app.create_request(user=u, loan_type=lt, requested_amount=10_000_000, installments_count=12)
    r = auth(u).post(REQUESTS, {"loan_type": lt.id, "requested_amount": 5_000_000, "installments_count": 6}, format="json")
    assert r.status_code == 400  # already has an in-progress loan of this type


def test_employee_sees_only_own_requests(make_user, auth):
    from loan.application import services as app

    lt = _type()
    p1 = _person("0012345679")
    p2 = _person("1234567891")
    u1 = _linked(make_user, p1)
    u2 = _linked(make_user, p2)
    app.create_request(user=u1, loan_type=lt, requested_amount=10_000_000, installments_count=12)
    assert auth(u2).get(REQUESTS).data["count"] == 0


def test_approve_within_fund(make_user, make_role, grant_role, auth):
    from loan.application import services as app

    lt = _type(max_amount=100_000_000, budget=200_000_000, profit=0)
    person = _person()
    emp = _linked(make_user, person)
    req = app.create_request(user=emp, loan_type=lt, requested_amount=80_000_000, installments_count=20)
    expert = _expert(make_user, make_role, grant_role)
    r = auth(expert).post(f"{REQUESTS}/{req.id}/approve", {"approved_amount": 80_000_000}, format="json")
    assert r.status_code == 200
    assert r.data["status"] == "approved"
    assert r.data["approved_amount"] == 80_000_000
    assert r.data["monthly_installment"] == 4_000_000   # 80,000,000 / 20


def test_fund_budget_is_cumulative(make_user, make_role, grant_role, auth):
    from loan.application import services as app

    lt = _type(max_amount=100_000_000, budget=100_000_000, block=False)
    expert = _expert(make_user, make_role, grant_role)

    p1 = _person("0012345679")
    r1 = app.create_request(user=_linked(make_user, p1), loan_type=lt, requested_amount=70_000_000, installments_count=12)
    ok = auth(expert).post(f"{REQUESTS}/{r1.id}/approve", {"approved_amount": 70_000_000}, format="json")
    assert ok.status_code == 200

    p2 = _person("1234567891")
    r2 = app.create_request(user=_linked(make_user, p2, mobile="09120000002"), loan_type=lt, requested_amount=60_000_000, installments_count=12)
    over = auth(expert).post(f"{REQUESTS}/{r2.id}/approve", {"approved_amount": 60_000_000}, format="json")
    assert over.status_code == 400  # only 30,000,000 of the fund remains


def test_employee_cannot_approve(make_user, auth):
    from loan.application import services as app

    lt = _type()
    person = _person()
    emp = _linked(make_user, person)
    req = app.create_request(user=emp, loan_type=lt, requested_amount=10_000_000, installments_count=12)
    r = auth(emp).post(f"{REQUESTS}/{req.id}/approve", {"approved_amount": 10_000_000}, format="json")
    assert r.status_code == 403


def test_disburse_flow(make_user, make_role, grant_role, auth):
    from loan.application import services as app

    lt = _type(budget=0)
    person = _person()
    emp = _linked(make_user, person)
    req = app.create_request(user=emp, loan_type=lt, requested_amount=10_000_000, installments_count=12)
    expert = _expert(make_user, make_role, grant_role)
    auth(expert).post(f"{REQUESTS}/{req.id}/approve", {}, format="json")
    d = auth(expert).post(f"{REQUESTS}/{req.id}/disburse", {}, format="json")
    assert d.status_code == 200 and d.data["status"] == "disbursed"


def test_loan_stats_are_real(seeded_rbac, make_user, superuser, auth):
    from loan.application import services as app

    lt = _type(budget=100_000_000)
    emp = _linked(make_user, _person())
    app.create_request(user=emp, loan_type=lt, requested_amount=10_000_000, installments_count=12)

    r = auth(superuser).get("/api/v1/me/dashboard/summary")
    assert r.data["loan.pending_requests"]["status"] == "ok"
    assert r.data["loan.pending_requests"]["value"] >= 1
    assert r.data["loan.credit_usage"]["status"] == "ok"


def test_request_rls_scoped_for_expert(make_user, make_role, grant_role, auth):
    from hr.models import OrgUnit, Province
    from loan.application import services as app

    pa = Province.objects.create(name="الف", code="PA")
    hq = OrgUnit.objects.create(name="HQ", code="HQ", type="hq")
    oa = OrgUnit.objects.create(name="A", code="OA", type="province_org", parent=hq, province=pa)
    ob = OrgUnit.objects.create(name="B", code="OB", type="province_org", parent=hq)
    lt = _type(block=False)

    pin = _person("0012345679", org_unit=oa)
    pout = _person("1234567891", org_unit=ob)
    app.create_request(user=_linked(make_user, pin), loan_type=lt, requested_amount=1_000_000, installments_count=6)
    app.create_request(user=_linked(make_user, pout, mobile="09120000002"), loan_type=lt, requested_amount=1_000_000, installments_count=6)

    expert = _expert(make_user, make_role, grant_role, mobile="09128888888", scope=oa.id)
    r = auth(expert).get(REQUESTS)
    persons = [row["personnel"] for row in r.data["results"]]
    assert pin.id in persons and pout.id not in persons

import pytest
from datetime import date

pytestmark = pytest.mark.django_db

BATCHES = "/api/v1/finance/batches"


def _person(nid="0012345679", org_unit=None):
    from hr.models import Personnel

    return Personnel.objects.create(
        national_id=nid, personnel_no=nid[-2:], first_name="ا", last_name="ب", org_unit=org_unit,
    )


def _disbursed_loan(person, installment=5_000_000):
    from loan.models import LoanRequest, LoanType

    lt = LoanType.objects.create(name="L", code=f"L-{person.national_id}", max_amount=100_000_000, max_installments=24)
    return LoanRequest.objects.create(
        loan_type=lt, personnel=person, requested_amount=60_000_000, approved_amount=60_000_000,
        monthly_installment=installment, installments_count=12, status=LoanRequest.DISBURSED,
        code=f"LN-{person.national_id}",
    )


def _approved_insurance(person, premium=1_200_000):
    from insurance.models import InsurancePlan, InsuranceRequest

    plan = InsurancePlan.objects.create(name="P", code=f"P-{person.national_id}", premium_per_person=premium, coverage_ceiling=100)
    return InsuranceRequest.objects.create(
        plan=plan, personnel=person, premium_total=premium, status=InsuranceRequest.APPROVED,
        code=f"INS-{person.national_id}",
    )


def _finance_user(make_user, make_role, grant_role, mobile="09129999999", scope=None):
    make_role("fin", permissions=["finance.export.view"])
    u = make_user(mobile=mobile)
    grant_role(u, "fin", scope_org_unit_id=scope)
    return u


def test_batch_create_requires_permission(make_user, auth):
    assert auth(make_user()).post(BATCHES, {"period": "1405-03"}, format="json").status_code == 403


def test_generate_pulls_loan_and_insurance(make_user, make_role, grant_role, auth):
    person = _person()
    _disbursed_loan(person, installment=5_000_000)
    _approved_insurance(person, premium=1_200_000)
    fin = _finance_user(make_user, make_role, grant_role)
    c = auth(fin)

    b = c.post(BATCHES, {"period": "1405-03", "title": "خرداد"}, format="json")
    assert b.status_code == 201
    bid = b.data["id"]

    gen = c.post(f"{BATCHES}/{bid}/generate", {}, format="json")
    assert gen.status_code == 200
    assert gen.data["item_count"] == 2                       # one loan + one insurance line
    assert gen.data["total_amount"] == 6_200_000            # 5,000,000 + 1,200,000


def test_items_and_manual_add(make_user, make_role, grant_role, auth):
    person = _person()
    _disbursed_loan(person, installment=3_000_000)
    fin = _finance_user(make_user, make_role, grant_role)
    c = auth(fin)
    bid = c.post(BATCHES, {"period": "1405-03"}, format="json").data["id"]
    c.post(f"{BATCHES}/{bid}/generate", {}, format="json")

    other = _person("1234567891")
    added = c.post(f"{BATCHES}/{bid}/add-item", {"personnel": other.id, "amount": 500_000, "description": "جریمه"}, format="json")
    assert added.status_code == 201

    items = c.get(f"{BATCHES}/{bid}/items")
    assert items.data["count"] == 2


def test_finalize_then_export_csv(make_user, make_role, grant_role, auth):
    person = _person()
    _disbursed_loan(person, installment=4_000_000)
    fin = _finance_user(make_user, make_role, grant_role)
    c = auth(fin)
    bid = c.post(BATCHES, {"period": "1405-03"}, format="json").data["id"]
    c.post(f"{BATCHES}/{bid}/generate", {}, format="json")

    fin_resp = c.post(f"{BATCHES}/{bid}/finalize", {}, format="json")
    assert fin_resp.status_code == 200 and fin_resp.data["status"] == "finalized"

    exp = c.get(f"{BATCHES}/{bid}/export")
    assert exp.status_code == 200
    assert exp["Content-Type"].startswith("text/csv")
    body = exp.content.decode("utf-8-sig")
    assert "جمع کل" in body


def test_finalize_empty_batch_rejected(make_user, make_role, grant_role, auth):
    fin = _finance_user(make_user, make_role, grant_role)
    c = auth(fin)
    bid = c.post(BATCHES, {"period": "1405-03"}, format="json").data["id"]
    r = c.post(f"{BATCHES}/{bid}/finalize", {}, format="json")
    assert r.status_code == 400


def test_monthly_deductions_stat_is_real(seeded_rbac, make_user, make_role, grant_role, superuser, auth):
    person = _person()
    _disbursed_loan(person, installment=7_000_000)
    fin = _finance_user(make_user, make_role, grant_role)
    bid = auth(fin).post(BATCHES, {"period": "1405-03"}, format="json").data["id"]
    auth(fin).post(f"{BATCHES}/{bid}/generate", {}, format="json")

    r = auth(superuser).get("/api/v1/me/dashboard/summary")
    assert r.data["finance.monthly_deductions"]["status"] == "ok"
    assert r.data["finance.monthly_deductions"]["value"] >= 7_000_000


def test_batches_rls_scoped(make_user, make_role, grant_role, auth):
    from hr.models import OrgUnit

    hq = OrgUnit.objects.create(name="HQ", code="HQ", type="hq")
    oa = OrgUnit.objects.create(name="A", code="OA", type="province_org", parent=hq)
    ob = OrgUnit.objects.create(name="B", code="OB", type="province_org", parent=hq)

    from finance.models import DeductionBatch

    DeductionBatch.objects.create(period="1405-03", org_unit=oa, title="A")
    DeductionBatch.objects.create(period="1405-03", org_unit=ob, title="B")

    fin = _finance_user(make_user, make_role, grant_role, scope=oa.id)
    r = auth(fin).get(BATCHES)
    titles = [row["title"] for row in r.data["results"]]
    assert "A" in titles and "B" not in titles

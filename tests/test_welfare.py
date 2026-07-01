import pytest
from datetime import date, timedelta

pytestmark = pytest.mark.django_db

ME = "/api/v1/welfare/profile/me"
NOTES = "/api/v1/welfare/notes"


def _person(nid="0012345679", org_unit=None):
    from hr.models import Personnel

    return Personnel.objects.create(
        national_id=nid, personnel_no=nid[-2:], first_name="ا", last_name="ب",
        org_unit=org_unit, birth_date=date(1985, 5, 5),
    )


def _linked(make_user, person, mobile=None):
    u = make_user(mobile=mobile or ("0912" + person.national_id[:7]))
    u.personnel_id = person.id
    u.save(update_fields=["personnel_id"])
    return u


def _welfare_expert(make_user, make_role, grant_role, mobile="09129999999", scope=None):
    make_role("wf", permissions=["welfare.profile.view"])
    e = make_user(mobile=mobile)
    grant_role(e, "wf", scope_org_unit_id=scope)
    return e


def _seed_services(person):
    """Give the personnel one of each welfare service to aggregate."""
    from accommodation.models import AccommodationComplex, AccommodationUnit, Reservation, UnitPlan
    from insurance.models import InsurancePlan, InsuranceRequest
    from loan.models import LoanRequest, LoanType
    from referral.models import ContractedProvider, ReferralLetter

    cx = AccommodationComplex.objects.create(name="C", code="C1")
    unit = AccommodationUnit.objects.create(complex=cx, plan=UnitPlan.objects.create(name="سوئیت"), name_or_number="1")
    Reservation.objects.create(
        unit=unit, personnel=person, check_in_date=date.today(), check_out_date=date.today() + timedelta(days=2),
        nights=2, status=Reservation.CONFIRMED, code="RSV-1",
    )
    plan = InsurancePlan.objects.create(name="P", code="P1", premium_per_person=1000, coverage_ceiling=100)
    InsuranceRequest.objects.create(plan=plan, personnel=person, status=InsuranceRequest.APPROVED, code="INS-1")
    lt = LoanType.objects.create(name="L", code="L1", max_amount=100, max_installments=12)
    LoanRequest.objects.create(
        loan_type=lt, personnel=person, requested_amount=100, approved_amount=100,
        monthly_installment=10, installments_count=10, status=LoanRequest.DISBURSED, code="LN-1",
    )
    prov = ContractedProvider.objects.create(name="G", code="G1")
    ReferralLetter.objects.create(
        provider=prov, personnel=person, service_description="x", status=ReferralLetter.ISSUED, code="REF-1"
    )


def test_my_profile_aggregates_all_modules(make_user, auth):
    person = _person()
    _linked_user = _linked(make_user, person)
    _seed_services(person)

    r = auth(_linked_user).get(ME)
    assert r.status_code == 200
    assert r.data["personnel"]["full_name"] == person.full_name
    assert r.data["accommodation"]["total_reservations"] == 1
    assert r.data["insurance"]["active_policies"] == 1
    assert r.data["loans"]["active_loans"] == 1
    assert r.data["referrals"]["issued"] == 1
    assert "notes" not in r.data  # own view hides staff notes


def test_my_profile_requires_linked_personnel(make_user, auth):
    r = auth(make_user()).get(ME)
    assert r.status_code == 400


def test_expert_can_view_scoped_profile(make_user, make_role, grant_role, auth):
    from hr.models import OrgUnit, Province

    pa = Province.objects.create(name="الف", code="PA")
    hq = OrgUnit.objects.create(name="HQ", code="HQ", type="hq")
    oa = OrgUnit.objects.create(name="A", code="OA", type="province_org", parent=hq, province=pa)
    person = _person(org_unit=oa)

    expert = _welfare_expert(make_user, make_role, grant_role, scope=oa.id)
    r = auth(expert).get(f"/api/v1/welfare/profile/{person.id}")
    assert r.status_code == 200
    assert "notes" in r.data  # staff view includes notes


def test_expert_cannot_view_out_of_scope_profile(make_user, make_role, grant_role, auth):
    from hr.models import OrgUnit, Province

    hq = OrgUnit.objects.create(name="HQ", code="HQ", type="hq")
    oa = OrgUnit.objects.create(name="A", code="OA", type="province_org", parent=hq)
    ob = OrgUnit.objects.create(name="B", code="OB", type="province_org", parent=hq)
    person = _person(org_unit=ob)

    expert = _welfare_expert(make_user, make_role, grant_role, scope=oa.id)
    r = auth(expert).get(f"/api/v1/welfare/profile/{person.id}")
    assert r.status_code == 403


def test_employee_cannot_view_others_profile(make_user, auth):
    me = _person("0012345679")
    other = _person("1234567891")
    u = _linked(make_user, me)
    r = auth(u).get(f"/api/v1/welfare/profile/{other.id}")
    assert r.status_code == 403


def test_expert_can_add_note(make_user, make_role, grant_role, auth):
    person = _person()
    expert = _welfare_expert(make_user, make_role, grant_role)
    r = auth(expert).post(
        NOTES, {"personnel": person.id, "category": "flag", "text": "نیازمند رسیدگی"}, format="json"
    )
    assert r.status_code == 201
    assert r.data["author_name"] is not None


def test_employee_cannot_add_note(make_user, auth):
    person = _person()
    u = _linked(make_user, person)
    r = auth(u).post(NOTES, {"personnel": person.id, "category": "note", "text": "x"}, format="json")
    assert r.status_code == 403

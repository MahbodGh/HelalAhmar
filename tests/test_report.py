import pytest
from datetime import date, timedelta

pytestmark = pytest.mark.django_db

SUMMARY = "/api/v1/report/summary"
BY_PROVINCE = "/api/v1/report/services-by-province"
CRITICAL = "/api/v1/report/critical-missions"


def _province(name, code):
    from hr.models import Province

    return Province.objects.create(name=name, code=code)


def _org(code, province=None, parent=None, type="province_org"):
    from hr.models import OrgUnit

    return OrgUnit.objects.create(name=code, code=code, type=type, province=province, parent=parent)


def _person(nid, org_unit, province):
    from hr.models import Personnel

    return Personnel.objects.create(
        national_id=nid, personnel_no=nid[-3:], first_name="ا", last_name="ب",
        org_unit=org_unit, province=province, birth_date=date(1990, 1, 1),
    )


def _service_for(person):
    """Give a personnel one delivered service (a disbursed loan)."""
    from loan.models import LoanRequest, LoanType

    lt, _ = LoanType.objects.get_or_create(code="L1", defaults={"name": "L", "max_amount": 10, "max_installments": 6})
    LoanRequest.objects.create(
        loan_type=lt, personnel=person, requested_amount=10, approved_amount=10,
        monthly_installment=1, installments_count=6, status=LoanRequest.DISBURSED,
        code=f"LN-{person.national_id}",
    )


def _reporter(make_user, make_role, grant_role, scope=None):
    make_role("rep", permissions=["report.dashboard.view"])
    u = make_user(mobile="09121234567")
    grant_role(u, "rep", scope_org_unit_id=scope)
    return u


def test_report_requires_permission(make_user, auth):
    assert auth(make_user()).get(SUMMARY).status_code == 403


def test_summary_counts_services(make_user, make_role, grant_role, auth):
    pa = _province("الف", "PA")
    hq = _org("HQ", type="hq")
    oa = _org("OA", province=pa, parent=hq)
    p = _person("0012345679", oa, pa)
    _service_for(p)

    u = _reporter(make_user, make_role, grant_role)
    r = auth(u).get(SUMMARY)
    assert r.status_code == 200
    assert r.data["total_services"] >= 1
    assert "distribution_fairness" in r.data


def test_services_by_province_breakdown(make_user, make_role, grant_role, auth):
    pa, pb = _province("الف", "PA"), _province("ب", "PB")
    hq = _org("HQ", type="hq")
    oa = _org("OA", province=pa, parent=hq)
    ob = _org("OB", province=pb, parent=hq)
    _service_for(_person("0012345679", oa, pa))
    _person("1234567891", ob, pb)  # province B has personnel but no services

    u = _reporter(make_user, make_role, grant_role)
    rows = auth(u).get(BY_PROVINCE).data
    by_name = {row["province_name"]: row for row in rows}
    assert by_name["الف"]["services"] == 1
    assert by_name["ب"]["services"] == 0


def test_critical_missions_flags_underserved(make_user, make_role, grant_role, auth):
    pa, pb = _province("الف", "PA"), _province("ب", "PB")
    hq = _org("HQ", type="hq")
    oa = _org("OA", province=pa, parent=hq)
    ob = _org("OB", province=pb, parent=hq)
    _service_for(_person("0012345679", oa, pa))
    _person("1234567891", ob, pb)  # underserved province

    u = _reporter(make_user, make_role, grant_role)
    alerts = auth(u).get(CRITICAL).data
    assert any(a["category"] == "coverage" for a in alerts)


def test_report_is_rls_scoped(make_user, make_role, grant_role, auth):
    pa, pb = _province("الف", "PA"), _province("ب", "PB")
    hq = _org("HQ", type="hq")
    oa = _org("OA", province=pa, parent=hq)
    ob = _org("OB", province=pb, parent=hq)
    _service_for(_person("0012345679", oa, pa))
    _service_for(_person("1234567891", ob, pb))

    # reporter scoped to province A only sees A's single service
    u = _reporter(make_user, make_role, grant_role, scope=oa.id)
    r = auth(u).get(SUMMARY)
    assert r.data["total_services"] == 1


def test_report_stats_are_real(seeded_rbac, make_user, make_role, grant_role, superuser, auth):
    pa = _province("الف", "PA")
    hq = _org("HQ", type="hq")
    oa = _org("OA", province=pa, parent=hq)
    _service_for(_person("0012345679", oa, pa))

    r = auth(superuser).get("/api/v1/me/dashboard/summary")
    assert r.data["report.total_services"]["status"] == "ok"
    assert r.data["report.total_services"]["value"] >= 1
    assert r.data["report.distribution_fairness"]["status"] == "ok"
    assert isinstance(r.data["report.services_by_province"]["value"], list)

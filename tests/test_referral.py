import pytest
from datetime import date

pytestmark = pytest.mark.django_db

PROVIDERS = "/api/v1/referral/providers"
LETTERS = "/api/v1/referral/letters"


def _provider(code="PRV1", active=True):
    from referral.models import ContractedProvider

    return ContractedProvider.objects.create(name=code, code=code, category="medical", is_active=active)


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
    make_role("ref", permissions=["referral.letter.manage"])
    e = make_user(mobile=mobile)
    grant_role(e, "ref", scope_org_unit_id=scope)
    return e


# --- providers ------------------------------------------------------------- #
def test_provider_create_requires_manage(make_user, auth):
    assert auth(make_user()).post(PROVIDERS, {"name": "x", "code": "X1"}, format="json").status_code == 403


def test_provider_list_visible_to_employee(make_user, auth):
    _provider()
    r = auth(make_user()).get(f"{PROVIDERS}?active=1")
    assert r.status_code == 200 and r.data["count"] == 1


# --- letters --------------------------------------------------------------- #
def test_create_letter_starts_requested(make_user, auth):
    prov = _provider()
    person = _person()
    u = _linked(make_user, person)
    r = auth(u).post(LETTERS, {"provider": prov.id, "service_description": "ویزیت"}, format="json")
    assert r.status_code == 201
    assert r.data["status"] == "requested"
    assert r.data["code"].startswith("REF-")


def test_create_letter_inactive_provider_rejected(make_user, auth):
    prov = _provider(active=False)
    person = _person()
    u = _linked(make_user, person)
    r = auth(u).post(LETTERS, {"provider": prov.id, "service_description": "x"}, format="json")
    assert r.status_code == 400


def test_issue_letter_flow(make_user, make_role, grant_role, auth):
    from referral.application import services as app

    prov = _provider()
    person = _person()
    emp = _linked(make_user, person)
    letter = app.create_letter(user=emp, provider=prov, service_description="ویزیت")

    expert = _expert(make_user, make_role, grant_role)
    r = auth(expert).post(
        f"{LETTERS}/{letter.id}/issue", {"valid_until": "2026-12-01", "note": "صادر شد"}, format="json"
    )
    assert r.status_code == 200 and r.data["status"] == "issued"
    assert r.data["valid_until"] == "2026-12-01"

    used = auth(expert).post(f"{LETTERS}/{letter.id}/mark-used", {}, format="json")
    assert used.status_code == 200 and used.data["status"] == "used"


def test_employee_cannot_issue(make_user, auth):
    from referral.application import services as app

    prov = _provider()
    person = _person()
    emp = _linked(make_user, person)
    letter = app.create_letter(user=emp, provider=prov, service_description="x")
    r = auth(emp).post(f"{LETTERS}/{letter.id}/issue", {}, format="json")
    assert r.status_code == 403


def test_employee_sees_only_own_letters(make_user, auth):
    from referral.application import services as app

    prov = _provider()
    p1 = _person("0012345679")
    p2 = _person("1234567891")
    u1 = _linked(make_user, p1)
    u2 = _linked(make_user, p2)
    app.create_letter(user=u1, provider=prov, service_description="x")

    r = auth(u2).get(LETTERS)
    assert r.data["count"] == 0


def test_issued_count_stat_is_real(seeded_rbac, make_user, make_role, grant_role, superuser, auth):
    from referral.application import services as app

    prov = _provider()
    person = _person()
    emp = _linked(make_user, person)
    letter = app.create_letter(user=emp, provider=prov, service_description="x")
    app.issue_letter(letter, emp)

    r = auth(superuser).get("/api/v1/me/dashboard/summary")
    assert r.data["referral.issued_count"]["status"] == "ok"
    assert r.data["referral.issued_count"]["value"] >= 1


def test_letter_rls_scoped_for_expert(make_user, make_role, grant_role, auth):
    from hr.models import OrgUnit, Province
    from referral.application import services as app

    pa = Province.objects.create(name="الف", code="PA")
    hq = OrgUnit.objects.create(name="HQ", code="HQ", type="hq")
    oa = OrgUnit.objects.create(name="A", code="OA", type="province_org", parent=hq, province=pa)
    ob = OrgUnit.objects.create(name="B", code="OB", type="province_org", parent=hq)

    prov = _provider()
    pin = _person("0012345679", org_unit=oa)
    pout = _person("1234567891", org_unit=ob)
    app.create_letter(user=_linked(make_user, pin), provider=prov, service_description="x")
    app.create_letter(user=_linked(make_user, pout), provider=prov, service_description="x")

    expert = _expert(make_user, make_role, grant_role, mobile="09128888888", scope=oa.id)
    r = auth(expert).get(LETTERS)
    persons = [row["personnel"] for row in r.data["results"]]
    assert pin.id in persons and pout.id not in persons

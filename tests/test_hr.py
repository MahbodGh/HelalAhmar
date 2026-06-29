import pytest

pytestmark = pytest.mark.django_db

VALID_NID = "0012345679"
VALID_NID2 = "1234567891"
PERSONNEL = "/api/v1/hr/personnel/"


def test_provinces_list(make_user, auth):
    from hr.models import Province

    Province.objects.create(name="تهران", code="P08")
    r = auth(make_user()).get("/api/v1/hr/provinces")
    assert r.status_code == 200
    assert any(p["code"] == "P08" for p in r.data)


def test_personnel_create_rejects_invalid_national_id(superuser, auth):
    r = auth(superuser).post(
        PERSONNEL,
        {"national_id": "1111111111", "personnel_no": "1", "first_name": "ا", "last_name": "ب"},
        format="json",
    )
    assert r.status_code == 400


def test_personnel_create_ok_with_valid_national_id(superuser, auth):
    r = auth(superuser).post(
        PERSONNEL,
        {"national_id": VALID_NID, "personnel_no": "1", "first_name": "ا", "last_name": "ب"},
        format="json",
    )
    assert r.status_code == 201


def test_personnel_list_is_rls_scoped(make_user, make_role, grant_role, auth):
    from hr.models import OrgUnit, Personnel, Province

    pa = Province.objects.create(name="A", code="PA")
    pb = Province.objects.create(name="B", code="PB")
    hq = OrgUnit.objects.create(name="HQ", code="HQ", type="hq")
    org_a = OrgUnit.objects.create(name="A", code="OA", type="province_org", parent=hq, province=pa)
    org_b = OrgUnit.objects.create(name="B", code="OB", type="province_org", parent=hq, province=pb)
    Personnel.objects.create(national_id=VALID_NID, personnel_no="1", first_name="ا", last_name="الف", org_unit=org_a)
    Personnel.objects.create(national_id=VALID_NID2, personnel_no="2", first_name="ب", last_name="ب", org_unit=org_b)

    make_role("prov_viewer", permissions=["hr.personnel.view"])
    u = make_user()
    grant_role(u, "prov_viewer", scope_org_unit_id=org_a.id)

    r = auth(u).get(PERSONNEL)
    assert r.status_code == 200
    nos = [p["personnel_no"] for p in r.data["results"]]
    assert nos == ["1"]  # only the scoped province's personnel


def test_super_admin_sees_all_personnel(superuser, auth):
    from hr.models import Personnel

    Personnel.objects.create(national_id=VALID_NID, personnel_no="1", first_name="ا", last_name="ب")
    Personnel.objects.create(national_id=VALID_NID2, personnel_no="2", first_name="ب", last_name="پ")
    r = auth(superuser).get(PERSONNEL)
    assert r.data["count"] == 2


def test_dependent_duplicate_national_id_rejected(superuser, auth):
    from hr.models import Personnel

    p = Personnel.objects.create(national_id=VALID_NID, personnel_no="1", first_name="ا", last_name="ب")
    c = auth(superuser)
    base = f"{PERSONNEL}{p.id}/dependents/"
    first = c.post(base, {"relation": "spouse", "first_name": "س", "last_name": "پ", "national_id": VALID_NID2}, format="json")
    assert first.status_code == 201
    dup = c.post(base, {"relation": "child", "first_name": "ف", "last_name": "پ", "national_id": VALID_NID2}, format="json")
    assert dup.status_code == 400

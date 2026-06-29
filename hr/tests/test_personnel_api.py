"""Tests for personnel API, permissions, RLS scoping, org tree and import."""
import pytest

pytestmark = pytest.mark.django_db


def _personnel(org_unit, national_id, personnel_no):
    from hr.models import Personnel

    return Personnel.objects.create(
        national_id=national_id, personnel_no=personnel_no,
        first_name="نام", last_name="خانوادگی", org_unit=org_unit,
    )


def test_personnel_create_requires_manage(make_user, auth_client, rbac, assign_role, superuser, make_nid):
    viewer = make_user(mobile="09120000020")
    assign_role(viewer, "province_welfare_expert")  # has hr.personnel.view, not manage
    payload = {"national_id": make_nid("123456781"), "personnel_no": "P100", "first_name": "a", "last_name": "b"}
    assert auth_client(viewer).post("/api/v1/hr/personnel", payload, format="json").status_code == 403
    assert auth_client(superuser).post("/api/v1/hr/personnel", payload, format="json").status_code == 201


def test_personnel_list_rls_scoping(make_user, auth_client, rbac, hr_base, assign_role, make_nid):
    from hr.models import OrgUnit

    org_a = OrgUnit.objects.get(code="ORG-P08")  # تهران
    org_b = OrgUnit.objects.get(code="ORG-P27")  # مازندران
    _personnel(org_a, make_nid("123456781"), "PA1")
    _personnel(org_b, make_nid("123456790"), "PB1")

    u = make_user(mobile="09120000021")
    assign_role(u, "province_welfare_expert", scope=org_a.id)

    r = auth_client(u).get("/api/v1/hr/personnel")
    assert r.status_code == 200
    nos = [p["personnel_no"] for p in r.data["results"]]
    assert "PA1" in nos and "PB1" not in nos


def test_org_unit_tree(auth_client, rbac, hr_base, superuser):
    r = auth_client(superuser).get("/api/v1/hr/org-units/tree")
    assert r.status_code == 200
    assert r.data[0]["code"] == "HQ"
    assert len(r.data[0]["children"]) >= 1


def test_personnel_import(auth_client, rbac, superuser, make_nid):
    payload = {"records": [
        {"national_id": make_nid("123456781"), "personnel_no": "IM1", "first_name": "a", "last_name": "b"},
    ]}
    r = auth_client(superuser).post("/api/v1/hr/personnel/import", payload, format="json")
    assert r.status_code == 200
    assert r.data["created"] == 1


def test_invalid_national_id_rejected_on_create(auth_client, rbac, superuser):
    payload = {"national_id": "1111111111", "personnel_no": "BAD1", "first_name": "a", "last_name": "b"}
    r = auth_client(superuser).post("/api/v1/hr/personnel", payload, format="json")
    assert r.status_code == 400

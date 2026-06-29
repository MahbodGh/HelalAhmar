import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def test_seed_rbac_counts():
    from identity.models import Dashboard, DashboardWidget, Permission, Role

    call_command("seed_rbac")
    assert Permission.objects.count() == 20
    assert Role.objects.count() == 16
    assert Dashboard.objects.count() == 16
    assert DashboardWidget.objects.count() == 41


def test_seed_rbac_is_idempotent():
    from identity.models import Role

    call_command("seed_rbac")
    call_command("seed_rbac")
    assert Role.objects.count() == 16  # no duplicates on re-run


def test_seed_hr_counts():
    from hr.models import OrgUnit, Province

    call_command("seed_hr")
    assert Province.objects.count() == 31
    assert OrgUnit.objects.count() == 32  # HQ + 31 province org units


def test_seed_accommodation_counts():
    from accommodation.models import Amenity, UnitPlan

    call_command("seed_accommodation")
    assert Amenity.objects.count() == 15  # 7 general + 8 unit
    assert UnitPlan.objects.count() == 6


def test_super_admin_role_has_all_permissions():
    from identity.models import Permission, Role

    call_command("seed_rbac")
    sa = Role.objects.get(code="super_admin")
    assert sa.permissions.count() == Permission.objects.count()

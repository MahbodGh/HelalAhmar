"""Shared fixtures for the test suite."""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture(autouse=True)
def fixed_otp(monkeypatch):
    """Make OTP codes deterministic ('123456') across the whole suite."""
    monkeypatch.setattr(
        "identity.application.services.generate_numeric_code",
        lambda length=6: "123456",
    )
    return "123456"


@pytest.fixture
def make_user(db):
    from identity.models import User

    def _make(mobile="09120000000", full_name="کاربر تست", is_active=True, **kw):
        return User.objects.create_user(mobile=mobile, full_name=full_name, is_active=is_active, **kw)

    return _make


@pytest.fixture
def superuser(db):
    from identity.models import User

    return User.objects.create_superuser(mobile="09129999999", password="x")


@pytest.fixture
def make_permission(db):
    from identity.models import Permission

    def _make(code, name=None, module=""):
        return Permission.objects.get_or_create(code=code, defaults={"name": name or code, "module": module})[0]

    return _make


@pytest.fixture
def make_role(db):
    from identity.models import Permission, Role

    def _make(code, name=None, permissions=()):
        role = Role.objects.get_or_create(code=code, defaults={"name": name or code})[0]
        if permissions:
            perms = [Permission.objects.get_or_create(code=c, defaults={"name": c})[0] for c in permissions]
            role.permissions.set(perms)
        return role

    return _make


@pytest.fixture
def grant_role(db):
    from identity.application import services as app

    def _grant(user, role_code, scope_org_unit_id=None):
        return app.assign_role(user, role_code, scope_org_unit_id)

    return _grant


@pytest.fixture
def auth(api):
    def _auth(user):
        api.force_authenticate(user=user)
        return api

    return _auth


@pytest.fixture
def seeded_rbac(db):
    """Run the full RBAC seed (permissions, roles, dashboards, widgets)."""
    from django.core.management import call_command

    call_command("seed_rbac")

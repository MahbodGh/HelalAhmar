"""Shared pytest fixtures for the whole project."""
import pytest
from django.core.management import call_command
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def make_user(db):
    from identity.models import User

    def _make(mobile="09120000000", full_name="", **kw):
        return User.objects.create_user(mobile=mobile, full_name=full_name, **kw)

    return _make


@pytest.fixture
def superuser(db):
    from identity.models import User

    return User.objects.create_superuser(mobile="09129999999", password="testpass123")


@pytest.fixture
def auth_client():
    """Return an APIClient authenticated as the given user (bypasses JWT)."""

    def _make(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _make


@pytest.fixture
def assign_role(db):
    from identity.application.services import assign_role as _assign

    def _make(user, role_code, scope=None):
        return _assign(user, role_code, scope)

    return _make


@pytest.fixture
def rbac(db):
    """Seed roles, permissions, dashboards and widgets."""
    call_command("seed_rbac")


@pytest.fixture
def hr_base(db):
    """Seed provinces and the base org tree (HQ + province units)."""
    call_command("seed_hr")


@pytest.fixture
def make_nid():
    """Build a checksum-valid Iranian national id from the first 9 digits."""

    def _make(first9="123456780"):
        check = sum(int(first9[i]) * (10 - i) for i in range(9)) % 11
        ctrl = check if check < 2 else 11 - check
        return first9 + str(ctrl)

    return _make

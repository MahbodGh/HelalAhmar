"""Accommodation application layer — RLS scope resolution."""
from __future__ import annotations

from accommodation.models import AccommodationComplex, AccommodationUnit
from hr.models import OrgUnit

_SCOPE_PERMS = [
    "accommodation.complex.view", "accommodation.complex.manage",
    "accommodation.reservation.manage", "accommodation.checkin.manage",
    "accommodation.housekeeping.manage", "accommodation.bi.view",
]


def complex_scope_ids(user) -> set[int] | None:
    """Org-unit ids whose complexes the user may see (None = all)."""
    if getattr(user, "is_super_admin", False):
        return None
    from identity.models import UserRole  # lazy

    scopes = (
        UserRole.objects.filter(
            user=user, is_active=True, role__permissions__code__in=_SCOPE_PERMS
        )
        .values_list("scope_org_unit_id", flat=True)
        .distinct()
    )
    allowed: set[int] = set()
    for sid in scopes:
        if sid is None:
            return None
        allowed |= OrgUnit.subtree_ids(sid)
    return allowed


def scoped_complex_qs(user):
    qs = AccommodationComplex.objects.select_related("province", "org_unit", "city").all()
    allowed = complex_scope_ids(user)
    return qs if allowed is None else qs.filter(org_unit_id__in=allowed)


def scoped_unit_qs(user):
    qs = AccommodationUnit.objects.select_related("complex", "plan").all()
    allowed = complex_scope_ids(user)
    return qs if allowed is None else qs.filter(complex__org_unit_id__in=allowed)

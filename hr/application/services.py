"""HR application layer — scope/RLS resolution and HR-sync use cases."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from hr.models import OrgUnit, Personnel


def personnel_scope_ids(user) -> set[int] | None:
    """
    Org-unit ids a user may see personnel from (RLS).
    Returns None = no restriction (sees all). Only roles granting
    'hr.personnel.view' contribute; a null scope on such a role = global.
    """
    if getattr(user, "is_super_admin", False):
        return None

    from identity.models import UserRole  # lazy: hr may load before identity ready

    scopes = (
        UserRole.objects.filter(
            user=user, is_active=True, role__permissions__code="hr.personnel.view"
        )
        .values_list("scope_org_unit_id", flat=True)
        .distinct()
    )
    allowed: set[int] = set()
    for sid in scopes:
        if sid is None:
            return None  # at least one global-scope role
        allowed |= OrgUnit.subtree_ids(sid)
    return allowed


def scoped_personnel_qs(user):
    """Personnel queryset limited to the user's org scope."""
    qs = Personnel.objects.select_related("org_unit", "province").all()
    allowed = personnel_scope_ids(user)
    if allowed is None:
        return qs
    return qs.filter(org_unit_id__in=allowed)


@transaction.atomic
def upsert_personnel(records: list[dict]) -> dict:
    """
    Bulk create/update personnel by national_id (stand-in for the HR-system sync).
    Each record needs at least national_id and personnel_no.
    """
    created = updated = 0
    now = timezone.now()
    for rec in records:
        nid = str(rec.get("national_id", "")).strip()
        if not nid:
            continue
        defaults = {k: v for k, v in rec.items() if k != "national_id"}
        defaults["last_synced_at"] = now
        _, was_created = Personnel.objects.update_or_create(
            national_id=nid, defaults=defaults
        )
        created += int(was_created)
        updated += int(not was_created)
    return {"created": created, "updated": updated, "total": len(records)}

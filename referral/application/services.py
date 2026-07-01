"""Referral application layer — RLS scope, letter workflow, dashboard stats."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from hr.models import OrgUnit, Personnel
from referral.models import ContractedProvider, ReferralLetter

MANAGE = "referral.letter.manage"


class ReferralError(Exception):
    """Validation/business-rule failure -> HTTP 400."""


def _user_perms(user) -> set[str]:
    from identity.application.services import get_user_roles
    return set(get_user_roles(user)["permissions"])


def _can_manage(user) -> bool:
    return getattr(user, "is_super_admin", False) or MANAGE in _user_perms(user)


def self_personnel(user):
    if not user.personnel_id:
        return None
    return Personnel.objects.filter(id=user.personnel_id).first()


def request_scope_org_ids(user) -> set[int] | None:
    if getattr(user, "is_super_admin", False):
        return None
    from identity.models import UserRole

    scopes = (
        UserRole.objects.filter(user=user, is_active=True, role__permissions__code=MANAGE)
        .values_list("scope_org_unit_id", flat=True)
        .distinct()
    )
    allowed: set[int] = set()
    for sid in scopes:
        if sid is None:
            return None
        allowed |= OrgUnit.subtree_ids(sid)
    return allowed


def scoped_letters(user):
    qs = ReferralLetter.objects.select_related("provider", "personnel", "personnel__org_unit", "beneficiary_dependent")
    if getattr(user, "is_super_admin", False):
        return qs
    if MANAGE in _user_perms(user):
        allowed = request_scope_org_ids(user)
        return qs if allowed is None else qs.filter(personnel__org_unit_id__in=allowed)
    return qs.filter(personnel_id=user.personnel_id) if user.personnel_id else qs.none()


@transaction.atomic
def create_letter(*, user, provider, service_description, beneficiary_dependent_id=None, note="", personnel=None):
    if personnel is not None and not _can_manage(user):
        raise ReferralError("اجازهٔ ثبت معرفی‌نامه برای دیگران را ندارید.")
    beneficiary = personnel or self_personnel(user)
    if beneficiary is None:
        raise ReferralError("به این کاربر پرسنلی متصل نیست.")
    if not provider.is_active:
        raise ReferralError("این مرکز طرف‌قرارداد فعال نیست.")

    dep = None
    if beneficiary_dependent_id:
        dep = beneficiary.dependents.filter(id=beneficiary_dependent_id).first()
        if dep is None:
            raise ReferralError("فرد تحت تکفل انتخابی معتبر نیست.")

    letter = ReferralLetter.objects.create(
        provider=provider, personnel=beneficiary, beneficiary_dependent=dep, created_by=user,
        service_description=service_description, note=note or "", status=ReferralLetter.REQUESTED,
    )
    letter.code = f"REF-{letter.id:06d}"
    letter.save(update_fields=["code"])
    return letter


@transaction.atomic
def issue_letter(letter, issuer, valid_until=None, note=""):
    if letter.status != ReferralLetter.REQUESTED:
        raise ReferralError("فقط معرفی‌نامهٔ درخواست‌شده قابل صدور است.")
    letter.status = ReferralLetter.ISSUED
    letter.issued_at = timezone.now()
    letter.issued_by = issuer
    letter.valid_until = valid_until
    letter.review_note = note or ""
    letter.save(update_fields=["status", "issued_at", "issued_by", "valid_until", "review_note"])
    return letter


@transaction.atomic
def reject_letter(letter, issuer, note=""):
    if letter.status != ReferralLetter.REQUESTED:
        raise ReferralError("فقط معرفی‌نامهٔ درخواست‌شده قابل رد است.")
    letter.status = ReferralLetter.REJECTED
    letter.issued_by = issuer
    letter.review_note = note or ""
    letter.save(update_fields=["status", "issued_by", "review_note"])
    return letter


@transaction.atomic
def mark_used(letter):
    if letter.status != ReferralLetter.ISSUED:
        raise ReferralError("فقط معرفی‌نامهٔ صادرشده قابل ثبت به‌عنوان استفاده‌شده است.")
    letter.status = ReferralLetter.USED
    letter.save(update_fields=["status"])
    return letter


@transaction.atomic
def cancel_letter(letter):
    if letter.status not in (ReferralLetter.REQUESTED, ReferralLetter.ISSUED):
        raise ReferralError("این معرفی‌نامه در وضعیتی نیست که قابل لغو باشد.")
    letter.status = ReferralLetter.CANCELLED
    letter.save(update_fields=["status"])
    return letter


# --------------------------------------------------------------------------- #
# Dashboard stats
# --------------------------------------------------------------------------- #
def resolve_stat(key: str, user) -> dict:
    if key == "referral.issued_count":
        n = scoped_letters(user).filter(status__in=[ReferralLetter.ISSUED, ReferralLetter.USED]).count()
        return {"value": n, "status": "ok", "unit": "معرفی‌نامه"}
    return {"value": None, "status": "pending"}

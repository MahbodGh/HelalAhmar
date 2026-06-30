"""Insurance application layer — RLS scope, request workflow, dashboard stats."""
from __future__ import annotations

from datetime import date

from django.db import transaction
from django.utils import timezone

from hr.models import Dependent, OrgUnit, Personnel
from insurance.models import InsurancePlan, InsuranceRequest

MANAGE = "insurance.request.manage"


class InsuranceError(Exception):
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
    """Org-unit subtree ids an insurance manager may see (None = all)."""
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


def scoped_requests(user):
    qs = InsuranceRequest.objects.select_related("plan", "personnel", "personnel__org_unit").prefetch_related("insured_dependents")
    if getattr(user, "is_super_admin", False):
        return qs
    if MANAGE in _user_perms(user):
        allowed = request_scope_org_ids(user)
        return qs if allowed is None else qs.filter(personnel__org_unit_id__in=allowed)
    return qs.filter(personnel_id=user.personnel_id) if user.personnel_id else qs.none()


@transaction.atomic
def create_request(*, user, plan, dependent_ids=None, coverage_start=None, coverage_end=None, personnel=None):
    if personnel is not None and not _can_manage(user):
        raise InsuranceError("اجازهٔ ثبت درخواست برای دیگران را ندارید.")
    beneficiary = personnel or self_personnel(user)
    if beneficiary is None:
        raise InsuranceError("به این کاربر پرسنلی متصل نیست.")
    if not plan.is_active:
        raise InsuranceError("این طرح فعال نیست.")

    dependent_ids = list(dict.fromkeys(dependent_ids or []))
    deps = list(Dependent.objects.filter(id__in=dependent_ids, personnel=beneficiary)) if dependent_ids else []
    if len(deps) != len(dependent_ids):
        raise InsuranceError("برخی از افراد تحت تکفل نامعتبرند یا متعلق به این پرسنل نیستند.")
    if deps and not plan.allow_dependents:
        raise InsuranceError("این طرح افراد تحت تکفل را نمی‌پذیرد.")
    if len(deps) > plan.max_dependents:
        raise InsuranceError(f"حداکثر {plan.max_dependents} نفر تحت تکفل مجاز است.")

    premium = plan.premium_per_person * (1 + len(deps))
    req = InsuranceRequest.objects.create(
        plan=plan, personnel=beneficiary, created_by=user, premium_total=premium,
        coverage_start=coverage_start, coverage_end=coverage_end,
        status=InsuranceRequest.SUBMITTED, submitted_at=timezone.now(),
    )
    if deps:
        req.insured_dependents.set(deps)
    req.code = f"INS-{req.id:06d}"
    req.save(update_fields=["code"])
    return req


@transaction.atomic
def cancel_request(request):
    if request.status not in (InsuranceRequest.DRAFT, InsuranceRequest.SUBMITTED):
        raise InsuranceError("این درخواست در وضعیتی نیست که قابل لغو باشد.")
    request.status = InsuranceRequest.CANCELLED
    request.save(update_fields=["status"])
    return request


@transaction.atomic
def approve_request(request, reviewer, note=""):
    if request.status != InsuranceRequest.SUBMITTED:
        raise InsuranceError("فقط درخواست در انتظار بررسی قابل تأیید است.")
    request.status = InsuranceRequest.APPROVED
    request.reviewed_by = reviewer
    request.reviewed_at = timezone.now()
    request.review_note = note or ""
    request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note"])
    return request


@transaction.atomic
def reject_request(request, reviewer, note=""):
    if request.status != InsuranceRequest.SUBMITTED:
        raise InsuranceError("فقط درخواست در انتظار بررسی قابل رد است.")
    request.status = InsuranceRequest.REJECTED
    request.reviewed_by = reviewer
    request.reviewed_at = timezone.now()
    request.review_note = note or ""
    request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note"])
    return request


# --------------------------------------------------------------------------- #
# Dashboard stats
# --------------------------------------------------------------------------- #
def _age(birth_date) -> int | None:
    if not birth_date:
        return None
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def high_risk_count(user, threshold=60) -> int:
    """Distinct insured people aged >= threshold across approved requests (scoped)."""
    reqs = (
        scoped_requests(user)
        .filter(status=InsuranceRequest.APPROVED)
        .select_related("personnel")
        .prefetch_related("insured_dependents")
    )
    seen: set[tuple[str, int]] = set()
    count = 0
    for r in reqs:
        a = _age(r.personnel.birth_date)
        if a is not None and a >= threshold and ("p", r.personnel_id) not in seen:
            seen.add(("p", r.personnel_id))
            count += 1
        for d in r.insured_dependents.all():
            da = _age(d.birth_date)
            if da is not None and da >= threshold and ("d", d.id) not in seen:
                seen.add(("d", d.id))
                count += 1
    return count


def resolve_stat(key: str, user) -> dict:
    if key == "insurance.pending_requests":
        n = scoped_requests(user).filter(status=InsuranceRequest.SUBMITTED).count()
        return {"value": n, "status": "ok", "unit": "درخواست"}
    if key == "insurance.high_risk_count":
        return {"value": high_risk_count(user), "status": "ok", "unit": "نفر"}
    return {"value": None, "status": "pending"}

"""Insurance application layer — RLS scope, request workflow, dashboard stats."""
from __future__ import annotations

from datetime import date

from django.db import transaction
from django.utils import timezone

from hr.models import Dependent, OrgUnit, Personnel
from insurance.models import InsuranceClaim, InsurancePlan, InsuranceRequest

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
# Claims (reimbursement against an approved policy)
# --------------------------------------------------------------------------- #
def scoped_claims(user):
    qs = InsuranceClaim.objects.select_related(
        "request", "request__plan", "personnel", "personnel__org_unit", "patient_dependent"
    )
    if getattr(user, "is_super_admin", False):
        return qs
    if MANAGE in _user_perms(user):
        allowed = request_scope_org_ids(user)
        return qs if allowed is None else qs.filter(personnel__org_unit_id__in=allowed)
    return qs.filter(personnel_id=user.personnel_id) if user.personnel_id else qs.none()


def policy_used_amount(request) -> int:
    """Sum of approved/paid claim amounts already committed against a policy."""
    from django.db.models import Sum
    agg = InsuranceClaim.objects.filter(
        request=request, status__in=[InsuranceClaim.APPROVED, InsuranceClaim.PAID]
    ).aggregate(s=Sum("approved_amount"))
    return agg["s"] or 0


def policy_remaining_ceiling(request) -> int:
    return max(request.plan.coverage_ceiling - policy_used_amount(request), 0)


@transaction.atomic
def create_claim(*, user, request, service_type, claimed_amount, service_date=None,
                 patient_dependent_id=None, description="", documents=None):
    # owner (or manager) only
    if not (getattr(user, "is_super_admin", False) or MANAGE in _user_perms(user)
            or request.personnel_id == user.personnel_id):
        raise InsuranceError("اجازهٔ ثبت خسارت برای این بیمه‌نامه را ندارید.")
    if request.status != InsuranceRequest.APPROVED:
        raise InsuranceError("فقط برای بیمه‌نامهٔ تأییدشده می‌توان خسارت ثبت کرد.")
    if not claimed_amount or claimed_amount <= 0:
        raise InsuranceError("مبلغ درخواستی باید بزرگ‌تر از صفر باشد.")

    patient = None
    if patient_dependent_id:
        patient = request.insured_dependents.filter(id=patient_dependent_id).first()
        if patient is None:
            raise InsuranceError("بیمار انتخابی جزو افراد تحت پوشش این بیمه‌نامه نیست.")

    claim = InsuranceClaim.objects.create(
        request=request, personnel=request.personnel, patient_dependent=patient, created_by=user,
        service_type=service_type, service_date=service_date, claimed_amount=claimed_amount,
        description=description or "", documents=documents or [],
        status=InsuranceClaim.SUBMITTED, submitted_at=timezone.now(),
    )
    claim.code = f"CLM-{claim.id:06d}"
    claim.save(update_fields=["code"])
    return claim


@transaction.atomic
def approve_claim(claim, reviewer, approved_amount, note=""):
    if claim.status != InsuranceClaim.SUBMITTED:
        raise InsuranceError("فقط خسارتِ در انتظار بررسی قابل تأیید است.")
    if approved_amount is None or approved_amount < 0:
        raise InsuranceError("مبلغ تأییدشده نامعتبر است.")
    if approved_amount > claim.claimed_amount:
        raise InsuranceError("مبلغ تأییدشده نمی‌تواند از مبلغ درخواستی بیشتر باشد.")
    remaining = policy_remaining_ceiling(claim.request)
    if approved_amount > remaining:
        raise InsuranceError(f"مبلغ تأییدشده از سقف باقی‌ماندهٔ تعهد ({remaining}) بیشتر است.")
    claim.status = InsuranceClaim.APPROVED
    claim.approved_amount = approved_amount
    claim.reviewed_by = reviewer
    claim.reviewed_at = timezone.now()
    claim.review_note = note or ""
    claim.save(update_fields=["status", "approved_amount", "reviewed_by", "reviewed_at", "review_note"])
    return claim


@transaction.atomic
def reject_claim(claim, reviewer, note=""):
    if claim.status != InsuranceClaim.SUBMITTED:
        raise InsuranceError("فقط خسارتِ در انتظار بررسی قابل رد است.")
    claim.status = InsuranceClaim.REJECTED
    claim.approved_amount = 0
    claim.reviewed_by = reviewer
    claim.reviewed_at = timezone.now()
    claim.review_note = note or ""
    claim.save(update_fields=["status", "approved_amount", "reviewed_by", "reviewed_at", "review_note"])
    return claim


@transaction.atomic
def mark_claim_paid(claim):
    if claim.status != InsuranceClaim.APPROVED:
        raise InsuranceError("فقط خسارتِ تأییدشده قابل پرداخت است.")
    claim.status = InsuranceClaim.PAID
    claim.paid_at = timezone.now()
    claim.save(update_fields=["status", "paid_at"])
    return claim


@transaction.atomic
def cancel_claim(claim):
    if claim.status not in (InsuranceClaim.SUBMITTED,):
        raise InsuranceError("فقط خسارتِ در انتظار بررسی قابل لغو است.")
    claim.status = InsuranceClaim.CANCELLED
    claim.save(update_fields=["status"])
    return claim


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
        pending_enroll = scoped_requests(user).filter(status=InsuranceRequest.SUBMITTED).count()
        pending_claims = scoped_claims(user).filter(status=InsuranceClaim.SUBMITTED).count()
        return {"value": pending_enroll + pending_claims, "status": "ok", "unit": "مورد"}
    if key == "insurance.high_risk_count":
        return {"value": high_risk_count(user), "status": "ok", "unit": "نفر"}
    return {"value": None, "status": "pending"}

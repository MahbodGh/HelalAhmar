"""Loan application layer — RLS scope, request workflow, fund budget, stats."""
from __future__ import annotations

import math

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from hr.models import OrgUnit, Personnel
from loan.models import LoanRequest, LoanType

MANAGE = "loan.request.manage"


class LoanError(Exception):
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


def scoped_requests(user):
    qs = LoanRequest.objects.select_related("loan_type", "personnel", "personnel__org_unit")
    if getattr(user, "is_super_admin", False):
        return qs
    if MANAGE in _user_perms(user):
        allowed = request_scope_org_ids(user)
        return qs if allowed is None else qs.filter(personnel__org_unit_id__in=allowed)
    return qs.filter(personnel_id=user.personnel_id) if user.personnel_id else qs.none()


def installment_amount(amount: int, installments: int, profit_rate: int) -> int:
    if installments <= 0:
        return 0
    total_payable = amount * (100 + profit_rate) / 100
    return int(math.ceil(total_payable / installments))


def fund_used(loan_type) -> int:
    agg = LoanRequest.objects.filter(
        loan_type=loan_type, status__in=LoanRequest.COMMITTING
    ).aggregate(s=Sum("approved_amount"))
    return agg["s"] or 0


def fund_remaining(loan_type) -> int:
    if not loan_type.fund_budget:
        return None  # unlimited
    return max(loan_type.fund_budget - fund_used(loan_type), 0)


def _eligible(personnel, rules: dict) -> bool:
    if not rules:
        return True
    if "employment_type" in rules and personnel.employment_type not in rules["employment_type"]:
        return False
    if "min_service_years" in rules and (personnel.computed_service_years or 0) < rules["min_service_years"]:
        return False
    return True


@transaction.atomic
def create_request(*, user, loan_type, requested_amount, installments_count, reason="", personnel=None):
    if personnel is not None and not _can_manage(user):
        raise LoanError("اجازهٔ ثبت درخواست برای دیگران را ندارید.")
    beneficiary = personnel or self_personnel(user)
    if beneficiary is None:
        raise LoanError("به این کاربر پرسنلی متصل نیست.")
    if not loan_type.is_active:
        raise LoanError("این نوع وام فعال نیست.")
    if not requested_amount or requested_amount <= 0:
        raise LoanError("مبلغ درخواستی باید بزرگ‌تر از صفر باشد.")
    if requested_amount > loan_type.max_amount:
        raise LoanError(f"مبلغ درخواستی از سقف مجاز ({loan_type.max_amount}) بیشتر است.")
    if installments_count < 1 or installments_count > loan_type.max_installments:
        raise LoanError(f"تعداد اقساط باید بین ۱ و {loan_type.max_installments} باشد.")
    if not _eligible(beneficiary, loan_type.audience_rules):
        raise LoanError("شما مشمول این نوع وام نیستید.")
    if loan_type.block_if_active_loan and LoanRequest.objects.filter(
        personnel=beneficiary, loan_type=loan_type,
        status__in=[LoanRequest.SUBMITTED, LoanRequest.APPROVED, LoanRequest.DISBURSED],
    ).exists():
        raise LoanError("شما یک وام فعال یا در جریان از این نوع دارید.")

    monthly = installment_amount(requested_amount, installments_count, loan_type.profit_rate)
    req = LoanRequest.objects.create(
        loan_type=loan_type, personnel=beneficiary, created_by=user,
        requested_amount=requested_amount, installments_count=installments_count,
        monthly_installment=monthly, reason=reason or "",
        status=LoanRequest.SUBMITTED, submitted_at=timezone.now(),
    )
    req.code = f"LN-{req.id:06d}"
    req.save(update_fields=["code"])
    return req


@transaction.atomic
def approve_request(request, reviewer, approved_amount=None, note=""):
    if request.status != LoanRequest.SUBMITTED:
        raise LoanError("فقط درخواست در انتظار بررسی قابل تأیید است.")
    amount = request.requested_amount if approved_amount is None else approved_amount
    if amount <= 0:
        raise LoanError("مبلغ مصوب نامعتبر است.")
    if amount > request.requested_amount:
        raise LoanError("مبلغ مصوب نمی‌تواند از مبلغ درخواستی بیشتر باشد.")
    remaining = fund_remaining(request.loan_type)
    if remaining is not None and amount > remaining:
        raise LoanError(f"مبلغ مصوب از اعتبار باقی‌ماندهٔ صندوق ({remaining}) بیشتر است.")

    request.approved_amount = amount
    request.monthly_installment = installment_amount(amount, request.installments_count, request.loan_type.profit_rate)
    request.status = LoanRequest.APPROVED
    request.reviewed_by = reviewer
    request.reviewed_at = timezone.now()
    request.review_note = note or ""
    request.save(update_fields=[
        "approved_amount", "monthly_installment", "status", "reviewed_by", "reviewed_at", "review_note",
    ])
    return request


@transaction.atomic
def reject_request(request, reviewer, note=""):
    if request.status != LoanRequest.SUBMITTED:
        raise LoanError("فقط درخواست در انتظار بررسی قابل رد است.")
    request.status = LoanRequest.REJECTED
    request.approved_amount = 0
    request.reviewed_by = reviewer
    request.reviewed_at = timezone.now()
    request.review_note = note or ""
    request.save(update_fields=["status", "approved_amount", "reviewed_by", "reviewed_at", "review_note"])
    return request


@transaction.atomic
def disburse_request(request):
    if request.status != LoanRequest.APPROVED:
        raise LoanError("فقط وام تأییدشده قابل پرداخت است.")
    request.status = LoanRequest.DISBURSED
    request.disbursed_at = timezone.now()
    request.save(update_fields=["status", "disbursed_at"])
    return request


@transaction.atomic
def cancel_request(request):
    if request.status not in (LoanRequest.SUBMITTED,):
        raise LoanError("فقط درخواست در انتظار بررسی قابل لغو است.")
    request.status = LoanRequest.CANCELLED
    request.save(update_fields=["status"])
    return request


# --------------------------------------------------------------------------- #
# Dashboard stats
# --------------------------------------------------------------------------- #
def credit_usage(user) -> float:
    used = scoped_requests(user).filter(
        status__in=LoanRequest.COMMITTING
    ).aggregate(s=Sum("approved_amount"))["s"] or 0
    budget = LoanType.objects.filter(is_active=True).aggregate(s=Sum("fund_budget"))["s"] or 0
    return round(used * 100 / budget, 1) if budget else 0


def resolve_stat(key: str, user) -> dict:
    if key == "loan.pending_requests":
        n = scoped_requests(user).filter(status=LoanRequest.SUBMITTED).count()
        return {"value": n, "status": "ok", "unit": "درخواست"}
    if key == "loan.credit_usage":
        return {"value": credit_usage(user), "status": "ok", "unit": "٪"}
    return {"value": None, "status": "pending"}

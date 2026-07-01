"""Finance application layer — build monthly deduction batches by pulling
loan installments + insurance premiums, finalize, export, and dashboard stats.
"""
from __future__ import annotations

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from finance.models import DeductionBatch, DeductionItem
from hr.models import OrgUnit

VIEW = "finance.export.view"


class FinanceError(Exception):
    pass


def _user_perms(user) -> set[str]:
    from identity.application.services import get_user_roles
    return set(get_user_roles(user)["permissions"])


def scope_org_ids(user) -> set[int] | None:
    if getattr(user, "is_super_admin", False):
        return None
    from identity.models import UserRole

    scopes = (
        UserRole.objects.filter(user=user, is_active=True, role__permissions__code=VIEW)
        .values_list("scope_org_unit_id", flat=True)
        .distinct()
    )
    allowed: set[int] = set()
    for sid in scopes:
        if sid is None:
            return None
        allowed |= OrgUnit.subtree_ids(sid)
    return allowed


def scoped_batches(user):
    qs = DeductionBatch.objects.select_related("org_unit").all()
    if getattr(user, "is_super_admin", False):
        return qs
    if VIEW in _user_perms(user):
        allowed = scope_org_ids(user)
        if allowed is None:
            return qs
        return qs.filter(Q(org_unit_id__in=allowed) | Q(org_unit__isnull=True))
    return qs.none()


def _batch_org_ids(batch) -> set[int] | None:
    return OrgUnit.subtree_ids(batch.org_unit_id) if batch.org_unit_id else None


def _recompute(batch):
    agg = batch.items.aggregate(s=Sum("amount"))
    batch.total_amount = agg["s"] or 0
    batch.item_count = batch.items.count()
    batch.save(update_fields=["total_amount", "item_count"])


@transaction.atomic
def generate_items(batch):
    """(Re)build deduction lines from disbursed loans + approved insurance policies."""
    if batch.status != DeductionBatch.DRAFT:
        raise FinanceError("فقط فایل پیش‌نویس قابل تولید مجدد است.")
    batch.items.all().delete()
    org_ids = _batch_org_ids(batch)

    from loan.models import LoanRequest
    loans = LoanRequest.objects.filter(status=LoanRequest.DISBURSED).select_related("personnel", "loan_type")
    if org_ids is not None:
        loans = loans.filter(personnel__org_unit_id__in=org_ids)
    for ln in loans:
        if ln.monthly_installment <= 0:
            continue
        DeductionItem.objects.create(
            batch=batch, personnel=ln.personnel, source_type=DeductionItem.LOAN,
            source_ref=ln.code, amount=ln.monthly_installment,
            description=f"قسط {ln.loan_type.name}",
        )

    from insurance.models import InsuranceRequest
    reqs = InsuranceRequest.objects.filter(status=InsuranceRequest.APPROVED).select_related("personnel", "plan")
    if org_ids is not None:
        reqs = reqs.filter(personnel__org_unit_id__in=org_ids)
    for r in reqs:
        if r.premium_total <= 0:
            continue
        DeductionItem.objects.create(
            batch=batch, personnel=r.personnel, source_type=DeductionItem.INSURANCE,
            source_ref=r.code, amount=r.premium_total, description="حق بیمهٔ تکمیلی",
        )

    batch.generated_at = timezone.now()
    batch.save(update_fields=["generated_at"])
    _recompute(batch)
    return batch


@transaction.atomic
def add_manual_item(batch, personnel, amount, description=""):
    if batch.status != DeductionBatch.DRAFT:
        raise FinanceError("فقط به فایل پیش‌نویس می‌توان قلم افزود.")
    if amount <= 0:
        raise FinanceError("مبلغ باید بزرگ‌تر از صفر باشد.")
    item = DeductionItem.objects.create(
        batch=batch, personnel=personnel, source_type=DeductionItem.MANUAL,
        amount=amount, description=description or "",
    )
    _recompute(batch)
    return item


@transaction.atomic
def finalize(batch):
    if batch.status != DeductionBatch.DRAFT:
        raise FinanceError("فقط فایل پیش‌نویس قابل نهایی‌سازی است.")
    if not batch.items.exists():
        raise FinanceError("فایل بدون قلم قابل نهایی‌سازی نیست.")
    batch.status = DeductionBatch.FINALIZED
    batch.finalized_at = timezone.now()
    batch.save(update_fields=["status", "finalized_at"])
    return batch


@transaction.atomic
def mark_exported(batch):
    batch.status = DeductionBatch.EXPORTED
    batch.exported_at = timezone.now()
    batch.save(update_fields=["status", "exported_at"])
    return batch


def scoped_items(user, batch):
    return batch.items.select_related("personnel").all()


# --------------------------------------------------------------------------- #
# Dashboard stats
# --------------------------------------------------------------------------- #
def monthly_deductions_total(user) -> int:
    batch = scoped_batches(user).order_by("-period", "-created_at").first()
    return batch.total_amount if batch else 0


def resolve_stat(key: str, user) -> dict:
    if key == "finance.monthly_deductions":
        return {"value": monthly_deductions_total(user), "status": "ok", "unit": "تومان"}
    return {"value": None, "status": "pending"}

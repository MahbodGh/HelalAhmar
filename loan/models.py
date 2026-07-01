from __future__ import annotations

from django.db import models

from shared.models import TimeStampedModel


class LoanType(TimeStampedModel):
    """A welfare-loan product with a ceiling, installments, and a fund budget."""

    FCFS = "fcfs"
    LOTTERY = "lottery"
    QUEUE = "queue"
    ALLOCATION_CHOICES = [
        (FCFS, "اولویت ثبت‌نام"),
        (LOTTERY, "قرعه‌کشی"),
        (QUEUE, "نوبت‌دهی"),
    ]

    name = models.CharField("عنوان وام", max_length=200)
    code = models.CharField("کد", max_length=30, unique=True)
    description = models.TextField("توضیحات", blank=True)

    max_amount = models.BigIntegerField("سقف مبلغ وام (تومان)", default=0)
    max_installments = models.PositiveSmallIntegerField("حداکثر تعداد اقساط", default=12)
    profit_rate = models.PositiveSmallIntegerField("نرخ کارمزد (درصد)", default=0)  # 0 = قرض‌الحسنه
    fund_budget = models.BigIntegerField("اعتبار کل صندوق (تومان)", default=0)  # 0 = نامحدود

    allocation_method = models.CharField("روش تخصیص", max_length=10, choices=ALLOCATION_CHOICES, default=FCFS)
    block_if_active_loan = models.BooleanField("منع در صورت داشتن وام فعال", default=True)
    audience_rules = models.JSONField("قواعد جامعهٔ هدف", default=dict, blank=True)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "نوع وام"
        verbose_name_plural = "انواع وام"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class LoanRequest(TimeStampedModel):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISBURSED = "disbursed"
    SETTLED = "settled"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (SUBMITTED, "در انتظار بررسی"),
        (APPROVED, "تأییدشده"),
        (REJECTED, "ردشده"),
        (DISBURSED, "پرداخت‌شده"),
        (SETTLED, "تسویه‌شده"),
        (CANCELLED, "لغوشده"),
    ]
    # statuses that consume the fund budget
    COMMITTING = [APPROVED, DISBURSED, SETTLED]

    code = models.CharField("کد درخواست", max_length=20, unique=True, blank=True)
    loan_type = models.ForeignKey(LoanType, on_delete=models.PROTECT, related_name="requests")
    personnel = models.ForeignKey("hr.Personnel", on_delete=models.PROTECT, related_name="loan_requests")
    created_by = models.ForeignKey("identity.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="created_loan_requests")

    requested_amount = models.BigIntegerField("مبلغ درخواستی (تومان)", default=0)
    installments_count = models.PositiveSmallIntegerField("تعداد اقساط", default=12)
    reason = models.TextField("علت درخواست", blank=True)

    approved_amount = models.BigIntegerField("مبلغ مصوب (تومان)", default=0)
    monthly_installment = models.BigIntegerField("مبلغ هر قسط (تومان)", default=0)

    status = models.CharField("وضعیت", max_length=12, choices=STATUS_CHOICES, default=SUBMITTED, db_index=True)
    submitted_at = models.DateTimeField("زمان ثبت", null=True, blank=True)
    reviewed_by = models.ForeignKey("identity.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="loan_reviews")
    reviewed_at = models.DateTimeField("زمان بررسی", null=True, blank=True)
    review_note = models.TextField("یادداشت بررسی", blank=True)
    disbursed_at = models.DateTimeField("زمان پرداخت", null=True, blank=True)

    class Meta:
        verbose_name = "درخواست وام"
        verbose_name_plural = "درخواست‌های وام"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.code or f"وام {self.pk}"

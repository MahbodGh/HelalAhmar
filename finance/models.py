from __future__ import annotations

from django.db import models

from shared.models import TimeStampedModel


class DeductionBatch(TimeStampedModel):
    """A monthly payroll-deduction run (فایل کسورات) covering an org scope."""

    DRAFT = "draft"
    FINALIZED = "finalized"
    EXPORTED = "exported"
    STATUS_CHOICES = [
        (DRAFT, "پیش‌نویس"),
        (FINALIZED, "نهایی‌شده"),
        (EXPORTED, "خروجی‌گرفته"),
    ]

    period = models.CharField("دورهٔ کسورات (مثل ۱۴۰۵-۰۳)", max_length=10, db_index=True)
    title = models.CharField("عنوان", max_length=200, blank=True)
    org_unit = models.ForeignKey("hr.OrgUnit", null=True, blank=True, on_delete=models.SET_NULL, related_name="deduction_batches")
    status = models.CharField("وضعیت", max_length=10, choices=STATUS_CHOICES, default=DRAFT, db_index=True)

    created_by = models.ForeignKey("identity.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="created_deduction_batches")
    generated_at = models.DateTimeField("زمان تولید اقلام", null=True, blank=True)
    finalized_at = models.DateTimeField("زمان نهایی‌سازی", null=True, blank=True)
    exported_at = models.DateTimeField("زمان خروجی", null=True, blank=True)

    total_amount = models.BigIntegerField("جمع کل (تومان)", default=0)
    item_count = models.PositiveIntegerField("تعداد اقلام", default=0)

    class Meta:
        verbose_name = "فایل کسورات"
        verbose_name_plural = "فایل‌های کسورات"
        ordering = ["-period", "-created_at"]

    def __str__(self) -> str:
        return f"{self.title or 'کسورات'} {self.period}"


class DeductionItem(TimeStampedModel):
    LOAN = "loan"
    INSURANCE = "insurance"
    ACCOMMODATION = "accommodation"
    MANUAL = "manual"
    OTHER = "other"
    SOURCE_CHOICES = [
        (LOAN, "قسط وام"),
        (INSURANCE, "حق بیمه"),
        (ACCOMMODATION, "هزینهٔ اقامت"),
        (MANUAL, "دستی"),
        (OTHER, "سایر"),
    ]

    batch = models.ForeignKey(DeductionBatch, on_delete=models.CASCADE, related_name="items")
    personnel = models.ForeignKey("hr.Personnel", on_delete=models.PROTECT, related_name="deduction_items")
    source_type = models.CharField("منشأ", max_length=15, choices=SOURCE_CHOICES, default=OTHER, db_index=True)
    source_ref = models.CharField("مرجع", max_length=30, blank=True)
    amount = models.BigIntegerField("مبلغ (تومان)", default=0)
    description = models.CharField("شرح", max_length=200, blank=True)

    class Meta:
        verbose_name = "قلم کسور"
        verbose_name_plural = "اقلام کسور"
        ordering = ["personnel_id", "source_type"]

    def __str__(self) -> str:
        return f"{self.personnel} - {self.amount}"

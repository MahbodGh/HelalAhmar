from __future__ import annotations

from django.db import models
from django.utils import timezone

from shared.models import TimeStampedModel


class InsurancePlan(TimeStampedModel):
    """A supplementary-insurance contract/plan the organization offers."""

    name = models.CharField("عنوان طرح", max_length=200)
    code = models.CharField("کد طرح", max_length=30, unique=True)
    insurer_name = models.CharField("شرکت بیمه‌گر", max_length=200, blank=True)
    description = models.TextField("توضیحات", blank=True)

    premium_per_person = models.BigIntegerField("حق بیمهٔ سرانه (تومان)", default=0)
    coverage_ceiling = models.BigIntegerField("سقف تعهد سالانه (تومان)", default=0)
    covered_services = models.JSONField("خدمات تحت پوشش", default=list, blank=True)

    contract_start = models.DateField("شروع قرارداد", null=True, blank=True)
    contract_end = models.DateField("پایان قرارداد", null=True, blank=True)

    allow_dependents = models.BooleanField("پذیرش افراد تحت تکفل", default=True)
    max_dependents = models.PositiveSmallIntegerField("حداکثر افراد تحت تکفل", default=10)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "طرح بیمه"
        verbose_name_plural = "طرح‌های بیمه"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class InsuranceRequest(TimeStampedModel):
    """An employee's request to be covered (self + dependents) under a plan."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (DRAFT, "پیش‌نویس"),
        (SUBMITTED, "در انتظار بررسی"),
        (APPROVED, "تأییدشده"),
        (REJECTED, "ردشده"),
        (CANCELLED, "لغوشده"),
    ]

    code = models.CharField("کد درخواست", max_length=20, unique=True, blank=True)
    plan = models.ForeignKey(InsurancePlan, on_delete=models.PROTECT, related_name="requests")
    personnel = models.ForeignKey("hr.Personnel", on_delete=models.PROTECT, related_name="insurance_requests")
    created_by = models.ForeignKey("identity.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="created_insurance_requests")
    insured_dependents = models.ManyToManyField("hr.Dependent", blank=True, related_name="insurance_requests")

    premium_total = models.BigIntegerField("حق بیمهٔ کل (تومان)", default=0)
    coverage_start = models.DateField("شروع پوشش", null=True, blank=True)
    coverage_end = models.DateField("پایان پوشش", null=True, blank=True)

    status = models.CharField("وضعیت", max_length=12, choices=STATUS_CHOICES, default=SUBMITTED, db_index=True)
    submitted_at = models.DateTimeField("زمان ثبت", null=True, blank=True)
    reviewed_by = models.ForeignKey("identity.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="insurance_reviews")
    reviewed_at = models.DateTimeField("زمان بررسی", null=True, blank=True)
    review_note = models.TextField("یادداشت بررسی", blank=True)

    class Meta:
        verbose_name = "درخواست بیمه"
        verbose_name_plural = "درخواست‌های بیمه"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.code or f"درخواست {self.pk}"

    @property
    def insured_count(self) -> int:
        return 1 + self.insured_dependents.count()


class InsuranceClaim(TimeStampedModel):
    """A reimbursement claim filed against an approved insurance policy (request)."""

    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (SUBMITTED, "در انتظار بررسی"),
        (APPROVED, "تأییدشده"),
        (REJECTED, "ردشده"),
        (PAID, "پرداخت‌شده"),
        (CANCELLED, "لغوشده"),
    ]

    code = models.CharField("کد خسارت", max_length=20, unique=True, blank=True)
    request = models.ForeignKey(InsuranceRequest, on_delete=models.PROTECT, related_name="claims")
    personnel = models.ForeignKey("hr.Personnel", on_delete=models.PROTECT, related_name="insurance_claims")
    # patient: null => the personnel themselves; otherwise one of the policy's insured dependents
    patient_dependent = models.ForeignKey("hr.Dependent", null=True, blank=True, on_delete=models.SET_NULL, related_name="insurance_claims")
    created_by = models.ForeignKey("identity.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="created_insurance_claims")

    service_type = models.CharField("نوع خدمت", max_length=100)
    service_date = models.DateField("تاریخ خدمت", null=True, blank=True)
    claimed_amount = models.BigIntegerField("مبلغ درخواستی (تومان)", default=0)
    approved_amount = models.BigIntegerField("مبلغ تأییدشده (تومان)", default=0)
    description = models.TextField("شرح", blank=True)
    documents = models.JSONField("مدارک", default=list, blank=True)

    status = models.CharField("وضعیت", max_length=12, choices=STATUS_CHOICES, default=SUBMITTED, db_index=True)
    submitted_at = models.DateTimeField("زمان ثبت", null=True, blank=True)
    reviewed_by = models.ForeignKey("identity.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="insurance_claim_reviews")
    reviewed_at = models.DateTimeField("زمان بررسی", null=True, blank=True)
    review_note = models.TextField("یادداشت بررسی", blank=True)
    paid_at = models.DateTimeField("زمان پرداخت", null=True, blank=True)

    class Meta:
        verbose_name = "درخواست خسارت"
        verbose_name_plural = "درخواست‌های خسارت"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.code or f"خسارت {self.pk}"

    @property
    def patient_name(self) -> str:
        return self.patient_dependent.full_name if self.patient_dependent else self.personnel.full_name

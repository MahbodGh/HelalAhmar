from __future__ import annotations

from django.db import models

from shared.models import TimeStampedModel


class ContractedProvider(TimeStampedModel):
    """A service center the organization has a contract with (طرف‌قرارداد)."""

    MEDICAL = "medical"
    PHARMACY = "pharmacy"
    CULTURAL = "cultural"
    SPORTS = "sports"
    EDUCATIONAL = "educational"
    TOURISM = "tourism"
    OTHER = "other"
    CATEGORY_CHOICES = [
        (MEDICAL, "درمانی"),
        (PHARMACY, "دارویی"),
        (CULTURAL, "فرهنگی"),
        (SPORTS, "ورزشی"),
        (EDUCATIONAL, "آموزشی"),
        (TOURISM, "گردشگری"),
        (OTHER, "سایر"),
    ]

    name = models.CharField("نام مرکز", max_length=200)
    code = models.CharField("کد", max_length=30, unique=True)
    category = models.CharField("دسته", max_length=15, choices=CATEGORY_CHOICES, default=OTHER, db_index=True)
    province = models.ForeignKey("hr.Province", null=True, blank=True, on_delete=models.SET_NULL, related_name="providers")
    city = models.ForeignKey("hr.City", null=True, blank=True, on_delete=models.SET_NULL, related_name="providers")
    address = models.CharField("نشانی", max_length=400, blank=True)
    phone = models.CharField("تلفن", max_length=30, blank=True)

    discount_percent = models.PositiveSmallIntegerField("درصد تخفیف", default=0)
    terms = models.TextField("شرایط قرارداد", blank=True)
    contract_start = models.DateField("شروع قرارداد", null=True, blank=True)
    contract_end = models.DateField("پایان قرارداد", null=True, blank=True)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "مرکز طرف‌قرارداد"
        verbose_name_plural = "مراکز طرف‌قرارداد"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ReferralLetter(TimeStampedModel):
    """A referral letter issued to a personnel to use a contracted provider."""

    REQUESTED = "requested"
    ISSUED = "issued"
    REJECTED = "rejected"
    USED = "used"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    STATUS_CHOICES = [
        (REQUESTED, "درخواست‌شده"),
        (ISSUED, "صادرشده"),
        (REJECTED, "ردشده"),
        (USED, "استفاده‌شده"),
        (CANCELLED, "لغوشده"),
        (EXPIRED, "منقضی"),
    ]

    code = models.CharField("کد معرفی‌نامه", max_length=20, unique=True, blank=True)
    provider = models.ForeignKey(ContractedProvider, on_delete=models.PROTECT, related_name="letters")
    personnel = models.ForeignKey("hr.Personnel", on_delete=models.PROTECT, related_name="referral_letters")
    beneficiary_dependent = models.ForeignKey("hr.Dependent", null=True, blank=True, on_delete=models.SET_NULL, related_name="referral_letters")
    created_by = models.ForeignKey("identity.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="created_referral_letters")

    service_description = models.CharField("شرح خدمت", max_length=300)
    note = models.TextField("توضیحات", blank=True)

    status = models.CharField("وضعیت", max_length=12, choices=STATUS_CHOICES, default=REQUESTED, db_index=True)
    issued_at = models.DateTimeField("زمان صدور", null=True, blank=True)
    issued_by = models.ForeignKey("identity.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="issued_referral_letters")
    valid_until = models.DateField("معتبر تا", null=True, blank=True)
    review_note = models.TextField("یادداشت بررسی", blank=True)

    class Meta:
        verbose_name = "معرفی‌نامه"
        verbose_name_plural = "معرفی‌نامه‌ها"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.code or f"معرفی‌نامه {self.pk}"

    @property
    def beneficiary_name(self) -> str:
        return self.beneficiary_dependent.full_name if self.beneficiary_dependent else self.personnel.full_name

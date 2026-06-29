"""Accommodation base layer: complexes, plans, units, amenities, rates."""
from __future__ import annotations

from django.db import models
from django.utils import timezone

from shared.models import TimeStampedModel


class Amenity(TimeStampedModel):
    SCOPE_CHOICES = [("general", "مجموعه"), ("unit", "واحد")]

    name = models.CharField("نام امکانات", max_length=100)
    scope = models.CharField("سطح", max_length=10, choices=SCOPE_CHOICES, default="general")
    icon = models.CharField("آیکن", max_length=60, blank=True)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "امکانات"
        verbose_name_plural = "امکانات"
        ordering = ["scope", "name"]

    def __str__(self) -> str:
        return self.name


class AccommodationComplex(TimeStampedModel):
    name = models.CharField("نام مجموعه", max_length=200)
    code = models.CharField("کد", max_length=40, unique=True)
    address = models.CharField("آدرس", max_length=400, blank=True)
    latitude = models.FloatField("عرض جغرافیایی", null=True, blank=True)
    longitude = models.FloatField("طول جغرافیایی", null=True, blank=True)
    phone = models.CharField("تلفن", max_length=30, blank=True)
    email = models.EmailField("ایمیل", blank=True)

    # org/geo for RLS
    org_unit = models.ForeignKey(
        "hr.OrgUnit", null=True, blank=True, on_delete=models.SET_NULL, related_name="complexes"
    )
    province = models.ForeignKey(
        "hr.Province", null=True, blank=True, on_delete=models.SET_NULL, related_name="complexes"
    )
    city = models.ForeignKey(
        "hr.City", null=True, blank=True, on_delete=models.SET_NULL, related_name="complexes"
    )

    manager = models.ForeignKey(
        "hr.Personnel", null=True, blank=True, on_delete=models.SET_NULL, related_name="managed_complexes"
    )
    executive_officer = models.ForeignKey(
        "hr.Personnel", null=True, blank=True, on_delete=models.SET_NULL, related_name="executive_complexes"
    )
    services_officer = models.ForeignKey(
        "hr.Personnel", null=True, blank=True, on_delete=models.SET_NULL, related_name="services_complexes"
    )
    housekeeping_staff = models.ManyToManyField(
        "hr.Personnel", blank=True, related_name="housekeeping_complexes"
    )
    general_amenities = models.ManyToManyField(Amenity, blank=True, related_name="complexes")
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "مجموعهٔ اقامتی"
        verbose_name_plural = "مجموعه‌های اقامتی"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class UnitPlan(TimeStampedModel):
    """نوع/پلان واحد به‌صورت داینامیک: سوئیت، اتاق، کلبه، تخت و ..."""

    name = models.CharField("نام پلان", max_length=100, unique=True)
    is_management = models.BooleanField("مدیریتی", default=False)
    description = models.CharField("توضیح", max_length=255, blank=True)

    class Meta:
        verbose_name = "پلان واحد"
        verbose_name_plural = "پلان‌های واحد"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class AccommodationUnit(TimeStampedModel):
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_MAINTENANCE = "maintenance"
    STATUS_CLEANING = "cleaning"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "فعال"),
        (STATUS_INACTIVE, "غیرفعال"),
        (STATUS_MAINTENANCE, "در دست تعمیر"),
        (STATUS_CLEANING, "در حال نظافت"),
    ]

    complex = models.ForeignKey(
        AccommodationComplex, on_delete=models.CASCADE, related_name="units"
    )
    plan = models.ForeignKey(UnitPlan, on_delete=models.PROTECT, related_name="units")
    name_or_number = models.CharField("نام/شماره واحد", max_length=50)
    standard_capacity = models.PositiveSmallIntegerField("ظرفیت استاندارد", default=1)
    max_capacity = models.PositiveSmallIntegerField("حداکثر ظرفیت", default=1)
    area_m2 = models.PositiveSmallIntegerField("متراژ", null=True, blank=True)
    amenities = models.ManyToManyField(Amenity, blank=True, related_name="units")
    status = models.CharField("وضعیت", max_length=15, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)
    is_management = models.BooleanField("مدیریتی", default=False)

    class Meta:
        verbose_name = "واحد اقامتی"
        verbose_name_plural = "واحدهای اقامتی"
        ordering = ["complex", "name_or_number"]
        constraints = [
            models.UniqueConstraint(fields=["complex", "name_or_number"], name="uniq_unit_in_complex")
        ]

    def __str__(self) -> str:
        return f"{self.complex.name} - {self.name_or_number}"


class SeasonalRate(TimeStampedModel):
    """نرخ‌گذاری فصلی هر واحد (مبلغ به تومان)."""

    unit = models.ForeignKey(AccommodationUnit, on_delete=models.CASCADE, related_name="rates")
    label = models.CharField("عنوان فصل", max_length=100, blank=True)
    date_from = models.DateField("از تاریخ")
    date_to = models.DateField("تا تاریخ")
    price = models.BigIntegerField("نرخ شبانه (تومان)", default=0)

    class Meta:
        verbose_name = "نرخ فصلی"
        verbose_name_plural = "نرخ‌های فصلی"
        ordering = ["unit", "date_from"]

    def __str__(self) -> str:
        return f"{self.unit} [{self.date_from}..{self.date_to}]"


# --------------------------------------------------------------------------- #
# Reservation periods + reservations (slice 2: FCFS)
# --------------------------------------------------------------------------- #
class ReservationPeriod(TimeStampedModel):
    METHOD_FCFS = "fcfs"
    METHOD_LOTTERY = "lottery"
    METHOD_ORG = "organizational"
    METHOD_CHOICES = [
        (METHOD_FCFS, "اولویت ثبت‌نام (FCFS)"),
        (METHOD_LOTTERY, "قرعه‌کشی"),
        (METHOD_ORG, "سازمانی"),
    ]
    STATUS_CHOICES = [("draft", "پیش‌نویس"), ("active", "فعال"), ("closed", "بسته")]
    SELECTION_CHOICES = [("user", "انتخاب کاربر"), ("random", "تخصیص تصادفی")]

    title = models.CharField("عنوان دوره", max_length=200)
    method = models.CharField("روش", max_length=20, choices=METHOD_CHOICES, default=METHOD_FCFS, db_index=True)
    status = models.CharField("وضعیت", max_length=10, choices=STATUS_CHOICES, default="draft", db_index=True)

    enroll_start = models.DateTimeField("شروع ثبت‌نام")
    enroll_end = models.DateTimeField("پایان ثبت‌نام")
    stay_from = models.DateField("شروع بازهٔ اقامت")
    stay_to = models.DateField("پایان بازهٔ اقامت")

    min_nights = models.PositiveSmallIntegerField("حداقل شب", default=1)
    max_nights = models.PositiveSmallIntegerField("حداکثر شب", default=7)
    max_total_companions = models.PositiveSmallIntegerField("حداکثر همراه", default=0)
    allowed_capacity_increase = models.PositiveSmallIntegerField("مجاز افزایش ظرفیت", default=0)
    block_if_used_within_days = models.PositiveSmallIntegerField("منع در صورت استفادهٔ اخیر (روز)", default=0)

    price_personnel = models.BigIntegerField("نرخ پرسنل (شب/تومان)", default=0)
    price_first_degree_companion = models.BigIntegerField("نرخ همراه درجه‌یک", default=0)
    price_other_companion = models.BigIntegerField("نرخ سایر همراهان", default=0)

    payment_methods = models.JSONField("روش‌های پرداخت مجاز", default=list, blank=True)
    payment_deadline_hours = models.PositiveSmallIntegerField("مهلت پرداخت (ساعت)", default=24)
    unit_selection_mode = models.CharField("نحوهٔ انتخاب واحد", max_length=10, choices=SELECTION_CHOICES, default="user")

    audience_rules = models.JSONField("قواعد جامعهٔ هدف", default=dict, blank=True)
    units = models.ManyToManyField(AccommodationUnit, blank=True, related_name="periods")

    org_unit = models.ForeignKey("hr.OrgUnit", null=True, blank=True, on_delete=models.SET_NULL, related_name="reservation_periods")
    province = models.ForeignKey("hr.Province", null=True, blank=True, on_delete=models.SET_NULL, related_name="reservation_periods")

    class Meta:
        verbose_name = "دورهٔ رزرو"
        verbose_name_plural = "دوره‌های رزرو"
        ordering = ["-enroll_start"]

    def __str__(self) -> str:
        return self.title

    @property
    def is_enroll_open(self) -> bool:
        now = timezone.now()
        return self.status == "active" and self.enroll_start <= now <= self.enroll_end


class Reservation(TimeStampedModel):
    PENDING_PAYMENT = "pending_payment"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    STATUS_CHOICES = [
        (PENDING_PAYMENT, "در انتظار پرداخت"),
        (CONFIRMED, "تأییدشده"),
        (CANCELLED, "لغوشده"),
        (EXPIRED, "منقضی"),
    ]

    code = models.CharField("کد رزرو", max_length=20, unique=True, blank=True)
    period = models.ForeignKey(ReservationPeriod, null=True, blank=True, on_delete=models.SET_NULL, related_name="reservations")
    unit = models.ForeignKey(AccommodationUnit, on_delete=models.PROTECT, related_name="reservations")
    personnel = models.ForeignKey("hr.Personnel", on_delete=models.PROTECT, related_name="reservations")
    created_by = models.ForeignKey("identity.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="created_reservations")

    check_in_date = models.DateField("تاریخ ورود")
    check_out_date = models.DateField("تاریخ خروج")
    nights = models.PositiveSmallIntegerField("تعداد شب", default=1)
    first_degree_companions = models.PositiveSmallIntegerField("همراه درجه‌یک", default=0)
    other_companions = models.PositiveSmallIntegerField("سایر همراهان", default=0)

    total_cost = models.BigIntegerField("هزینهٔ کل (تومان)", default=0)
    payment_method = models.CharField("روش پرداخت", max_length=20, blank=True)
    status = models.CharField("وضعیت", max_length=20, choices=STATUS_CHOICES, default=PENDING_PAYMENT, db_index=True)
    payment_deadline = models.DateTimeField("مهلت پرداخت", null=True, blank=True)
    is_refunded = models.BooleanField("بازگشت وجه", default=False)

    class Meta:
        verbose_name = "رزرو"
        verbose_name_plural = "رزروها"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["unit", "check_in_date", "check_out_date"])]

    def __str__(self) -> str:
        return self.code or f"رزرو {self.pk}"

    @property
    def persons(self) -> int:
        return 1 + self.first_degree_companions + self.other_companions

"""HR & Organization persistence layer."""
from __future__ import annotations

from datetime import date

from django.db import models

from shared.models import TimeStampedModel


# --------------------------------------------------------------------------- #
# Geography
# --------------------------------------------------------------------------- #
class Province(TimeStampedModel):
    name = models.CharField("نام استان", max_length=100, unique=True)
    code = models.CharField("کد", max_length=10, unique=True)

    class Meta:
        verbose_name = "استان"
        verbose_name_plural = "استان‌ها"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class City(TimeStampedModel):
    province = models.ForeignKey(Province, on_delete=models.CASCADE, related_name="cities")
    name = models.CharField("نام شهر", max_length=100)
    code = models.CharField("کد", max_length=10, blank=True)

    class Meta:
        verbose_name = "شهر"
        verbose_name_plural = "شهرها"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["province", "name"], name="uniq_city_in_province")
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.province.name})"


# --------------------------------------------------------------------------- #
# Organizational structure (hierarchical)
# --------------------------------------------------------------------------- #
class OrgUnit(TimeStampedModel):
    TYPE_CHOICES = [
        ("hq", "ستاد مرکزی"),
        ("province_org", "تشکیلات استان"),
        ("suborg", "سازمان زیرمجموعه"),
        ("department", "اداره"),
        ("unit", "واحد"),
        ("center", "مرکز"),
    ]

    name = models.CharField("نام", max_length=200)
    code = models.CharField("کد", max_length=40, unique=True)
    type = models.CharField("نوع", max_length=20, choices=TYPE_CHOICES, db_index=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    province = models.ForeignKey(
        Province, null=True, blank=True, on_delete=models.SET_NULL, related_name="org_units"
    )
    city = models.ForeignKey(
        City, null=True, blank=True, on_delete=models.SET_NULL, related_name="org_units"
    )
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "واحد سازمانی"
        verbose_name_plural = "واحدهای سازمانی"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @staticmethod
    def subtree_ids(root_id: int) -> set[int]:
        """All org-unit ids under root_id (inclusive). Basis for RLS / geo scope."""
        ids = {root_id}
        frontier = [root_id]
        while frontier:
            children = list(
                OrgUnit.objects.filter(parent_id__in=frontier).values_list("id", flat=True)
            )
            new = [c for c in children if c not in ids]
            ids.update(new)
            frontier = new
        return ids


# --------------------------------------------------------------------------- #
# Personnel (synced from the HR system; central entity for all welfare modules)
# --------------------------------------------------------------------------- #
class Personnel(TimeStampedModel):
    GENDER_CHOICES = [("m", "مرد"), ("f", "زن")]
    EMPLOYMENT_TYPE_CHOICES = [
        ("official", "رسمی"),
        ("contractual", "قراردادی"),
        ("contractor", "پیمانکاری"),
        ("volunteer", "داوطلب"),
        ("other", "سایر"),
    ]
    STATUS_CHOICES = [
        ("active", "شاغل"),
        ("retired", "بازنشسته"),
        ("terminated", "قطع همکاری"),
        ("suspended", "تعلیق"),
    ]

    national_id = models.CharField("کد ملی", max_length=10, unique=True, db_index=True)
    personnel_no = models.CharField("شماره پرسنلی", max_length=30, unique=True, db_index=True)
    first_name = models.CharField("نام", max_length=100)
    last_name = models.CharField("نام خانوادگی", max_length=100)
    gender = models.CharField("جنسیت", max_length=1, choices=GENDER_CHOICES, blank=True)
    birth_date = models.DateField("تاریخ تولد", null=True, blank=True)

    employment_type = models.CharField(
        "نوع استخدام", max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, blank=True, db_index=True
    )
    employment_status = models.CharField(
        "وضعیت اشتغال", max_length=20, choices=STATUS_CHOICES, default="active", db_index=True
    )
    hire_date = models.DateField("تاریخ جذب", null=True, blank=True)
    is_retired = models.BooleanField("بازنشسته", default=False)

    org_unit = models.ForeignKey(
        OrgUnit, null=True, blank=True, on_delete=models.SET_NULL, related_name="personnel"
    )
    province = models.ForeignKey(
        Province, null=True, blank=True, on_delete=models.SET_NULL, related_name="personnel"
    )
    job_title = models.CharField("عنوان شغلی", max_length=150, blank=True)
    children_count = models.PositiveSmallIntegerField("تعداد فرزند", default=0)
    service_years = models.PositiveSmallIntegerField("سابقه (سال)", null=True, blank=True)

    last_synced_at = models.DateTimeField("آخرین به‌روزرسانی از HR", null=True, blank=True)

    class Meta:
        verbose_name = "پرسنل"
        verbose_name_plural = "پرسنل"
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.personnel_no})"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def age(self) -> int | None:
        if not self.birth_date:
            return None
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )

    @property
    def computed_service_years(self) -> int | None:
        if self.service_years is not None:
            return self.service_years
        if not self.hire_date:
            return None
        today = date.today()
        return today.year - self.hire_date.year - (
            (today.month, today.day) < (self.hire_date.month, self.hire_date.day)
        )


class PersonnelDecree(TimeStampedModel):
    """احکام پرسنلی — flexible attributes used for target-audience rules."""

    personnel = models.ForeignKey(Personnel, on_delete=models.CASCADE, related_name="decrees")
    decree_no = models.CharField("شماره حکم", max_length=50, blank=True)
    decree_date = models.DateField("تاریخ حکم", null=True, blank=True)
    title = models.CharField("عنوان", max_length=200, blank=True)
    attributes = models.JSONField("مقادیر حکم", default=dict, blank=True)
    effective_from = models.DateField("از تاریخ", null=True, blank=True)
    effective_to = models.DateField("تا تاریخ", null=True, blank=True)

    class Meta:
        verbose_name = "حکم پرسنلی"
        verbose_name_plural = "احکام پرسنلی"
        ordering = ["-decree_date"]

    def __str__(self) -> str:
        return f"{self.personnel.full_name} - {self.title or self.decree_no}"


class Dependent(TimeStampedModel):
    """افراد تحت تکفل — registered once, reused across all welfare modules."""

    RELATION_CHOICES = [
        ("spouse", "همسر"),
        ("child", "فرزند"),
        ("father", "پدر"),
        ("mother", "مادر"),
        ("other", "سایر"),
    ]

    personnel = models.ForeignKey(Personnel, on_delete=models.CASCADE, related_name="dependents")
    relation = models.CharField("نسبت", max_length=10, choices=RELATION_CHOICES)
    first_name = models.CharField("نام", max_length=100)
    last_name = models.CharField("نام خانوادگی", max_length=100)
    national_id = models.CharField("کد ملی", max_length=10, unique=True, db_index=True)
    birth_date = models.DateField("تاریخ تولد", null=True, blank=True)
    gender = models.CharField("جنسیت", max_length=1, choices=Personnel.GENDER_CHOICES, blank=True)
    is_student = models.BooleanField("محصل/دانشجو", default=False)
    notes = models.CharField("توضیح", max_length=255, blank=True)

    class Meta:
        verbose_name = "فرد تحت تکفل"
        verbose_name_plural = "افراد تحت تکفل"
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} ({self.get_relation_display()})"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

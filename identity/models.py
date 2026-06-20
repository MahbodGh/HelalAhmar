"""
Identity persistence layer (ORM).
Kept in models.py (pragmatic DDD) so makemigrations & admin work out of the box.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from shared.models import TimeStampedModel


# --------------------------------------------------------------------------- #
# User
# --------------------------------------------------------------------------- #
class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, mobile: str, password=None, **extra):
        if not mobile:
            raise ValueError("mobile is required")
        user = self.model(mobile=mobile, **extra)
        if password:
            user.set_password(password)
        else:
            # OTP-only users have no usable password
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, mobile: str, password: str, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        if not password:
            raise ValueError("superuser must have a password (for the admin panel)")
        return self.create_user(mobile, password=password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Auth identity. Login identifier is the mobile number (OTP based).
    `is_superuser`/`is_staff` drive the Django super-admin panel.
    `personnel` link is nullable for now (filled after HR sync).
    """

    mobile = models.CharField("موبایل", max_length=13, unique=True, db_index=True)
    full_name = models.CharField("نام و نام خانوادگی", max_length=150, blank=True)

    # link to HR personnel record (added in a later bounded context); kept loose for now
    personnel_id = models.BigIntegerField(null=True, blank=True, db_index=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # may enter Django admin

    date_joined = models.DateTimeField(default=timezone.now)
    last_login_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "mobile"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"

    def __str__(self) -> str:
        return f"{self.full_name or self.mobile}"

    # convenience: does this user hold the super_admin role OR django superuser flag?
    @property
    def is_super_admin(self) -> bool:
        if self.is_superuser:
            return True
        return self.user_roles.filter(
            is_active=True, role__code=Role.SUPER_ADMIN_CODE
        ).exists()


# --------------------------------------------------------------------------- #
# RBAC
# --------------------------------------------------------------------------- #
class Permission(TimeStampedModel):
    """A fine-grained capability, e.g. 'accommodation.complex.create'."""

    code = models.CharField(max_length=120, unique=True)
    name = models.CharField(max_length=150)
    module = models.CharField(max_length=60, db_index=True, blank=True)

    class Meta:
        verbose_name = "دسترسی"
        verbose_name_plural = "دسترسی‌ها"
        ordering = ["module", "code"]

    def __str__(self) -> str:
        return self.code


class Role(TimeStampedModel):
    """A named bundle of permissions (RFP roles)."""

    SUPER_ADMIN_CODE = "super_admin"

    code = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)  # system roles can't be deleted
    permissions = models.ManyToManyField(Permission, related_name="roles", blank=True)

    class Meta:
        verbose_name = "نقش"
        verbose_name_plural = "نقش‌ها"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class UserRole(TimeStampedModel):
    """
    Assigns a role to a user, optionally scoped to an org unit (RLS / geo limit).
    scope_org_unit is a loose integer ref now; becomes FK when the Org context lands.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="user_roles")
    scope_org_unit_id = models.BigIntegerField(
        null=True, blank=True, help_text="null = دسترسی سراسری"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "انتساب نقش"
        verbose_name_plural = "انتساب نقش‌ها"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "scope_org_unit_id"],
                name="uniq_user_role_scope",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} → {self.role}"


# --------------------------------------------------------------------------- #
# Navigation / Dashboards (permission-gated menu)
# --------------------------------------------------------------------------- #
class Dashboard(TimeStampedModel):
    """
    A menu/dashboard entry shown to the frontend. Visible to a user only if its
    required_permission is in the user's permission set (null = everyone).
    Admin-manageable so new dashboards can be added without code.
    """

    code = models.CharField(max_length=80, unique=True)
    title = models.CharField("عنوان", max_length=150)
    description = models.TextField("توضیح", blank=True)
    icon = models.CharField("آیکن", max_length=60, blank=True, help_text="کلید آیکن سمت فرانت")
    route = models.CharField("مسیر", max_length=200, blank=True, help_text="route سمت فرانت")
    group = models.CharField("گروه منو", max_length=80, blank=True)
    required_permission = models.ForeignKey(
        Permission, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="dashboards", help_text="خالی = برای همهٔ کاربران واردشده",
    )
    order = models.PositiveIntegerField("ترتیب", default=0)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "داشبورد"
        verbose_name_plural = "داشبوردها"
        ordering = ["order", "title"]

    def __str__(self) -> str:
        return self.title


# --------------------------------------------------------------------------- #
# OTP
# --------------------------------------------------------------------------- #
class OtpRequest(models.Model):
    """A single OTP challenge. The plaintext code is never stored (hashed)."""

    PURPOSE_LOGIN = "login"
    PURPOSE_CHOICES = [(PURPOSE_LOGIN, "ورود")]

    mobile = models.CharField(max_length=13, db_index=True)
    code_hash = models.CharField(max_length=255)
    # Plaintext code, populated ONLY when DEBUG=True (dev/testing) so it can be
    # read from the admin panel. Stays empty in production (DEBUG=False).
    debug_code = models.CharField("کد (فقط حالت توسعه)", max_length=8, blank=True, default="")
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default=PURPOSE_LOGIN)

    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    is_used = models.BooleanField(default=False)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "درخواست کد یک‌بارمصرف"
        verbose_name_plural = "درخواست‌های کد یک‌بارمصرف"
        ordering = ["-created_at"]

    def set_code(self, raw_code: str) -> None:
        self.code_hash = make_password(raw_code)
        # dev-only: lets the admin panel show the code; never set in production
        if settings.DEBUG:
            self.debug_code = raw_code

    def check_code(self, raw_code: str) -> bool:
        return check_password(raw_code, self.code_hash)

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_valid(self) -> bool:
        return (
            not self.is_used
            and not self.is_expired
            and self.attempts < self.max_attempts
        )


class LoginAudit(models.Model):
    """Every login attempt — visible in the super-admin panel (RFP audit requirement)."""

    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="login_audits"
    )
    mobile = models.CharField(max_length=13, db_index=True)
    success = models.BooleanField(default=False)
    reason = models.CharField(max_length=120, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "لاگ ورود"
        verbose_name_plural = "لاگ‌های ورود"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        flag = "✅" if self.success else "❌"
        return f"{flag} {self.mobile} @ {self.created_at:%Y-%m-%d %H:%M}"

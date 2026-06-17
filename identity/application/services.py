"""
Application layer — orchestrates use cases. The API layer calls these,
never the ORM directly. Business rules + transactions live here.
"""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from identity.domain.services import generate_numeric_code, resolve_permissions
from identity.domain.value_objects import Mobile, OtpPolicy
from identity.infrastructure.sms import send_otp_sms
from identity.models import LoginAudit, OtpRequest, Role, User, UserRole


# --------------------------------------------------------------------------- #
# Errors (mapped to HTTP codes in the API layer)
# --------------------------------------------------------------------------- #
class OtpError(Exception):
    code = "otp_error"


class TooManyRequests(OtpError):
    code = "too_many_requests"


class InvalidOtp(OtpError):
    code = "invalid_otp"


class UserNotAllowed(OtpError):
    code = "user_not_allowed"


def _policy() -> OtpPolicy:
    return OtpPolicy(
        length=settings.OTP_LENGTH,
        ttl_seconds=settings.OTP_TTL_SECONDS,
        max_attempts=settings.OTP_MAX_ATTEMPTS,
        resend_cooldown_seconds=settings.OTP_RESEND_COOLDOWN_SECONDS,
        max_per_hour=settings.OTP_MAX_PER_HOUR,
    )


# --------------------------------------------------------------------------- #
# Use case: request an OTP
# --------------------------------------------------------------------------- #
@transaction.atomic
def request_otp(raw_mobile: str, ip: str | None = None) -> dict:
    mobile = Mobile.parse(raw_mobile)
    policy = _policy()
    now = timezone.now()

    # rate limiting
    recent = OtpRequest.objects.filter(
        mobile=mobile.value, created_at__gte=now - timedelta(hours=1)
    )
    if recent.count() >= policy.max_per_hour:
        raise TooManyRequests("تعداد درخواست‌ها در ساعت اخیر بیش از حد مجاز است.")

    last = recent.order_by("-created_at").first()
    if last and (now - last.created_at).total_seconds() < policy.resend_cooldown_seconds:
        wait = policy.resend_cooldown_seconds - int((now - last.created_at).total_seconds())
        raise TooManyRequests(f"برای ارسال مجدد {wait} ثانیه صبر کنید.")

    code = generate_numeric_code(policy.length)
    otp = OtpRequest(
        mobile=mobile.value,
        purpose=OtpRequest.PURPOSE_LOGIN,
        max_attempts=policy.max_attempts,
        ip_address=ip,
        expires_at=now + timedelta(seconds=policy.ttl_seconds),
    )
    otp.set_code(code)
    otp.save()

    send_otp_sms(mobile.value, code)
    result = {"expires_in": policy.ttl_seconds, "request_id": otp.id}
    if settings.DEBUG:
        # Dev convenience so you can test in Swagger without reading server logs.
        # Disappears automatically in production (DEBUG=False).
        result["debug_code"] = code
    return result


# --------------------------------------------------------------------------- #
# Use case: verify an OTP -> issue JWT
# --------------------------------------------------------------------------- #
@transaction.atomic
def verify_otp(raw_mobile: str, code: str, ip: str | None = None, user_agent: str = "") -> dict:
    mobile = Mobile.parse(raw_mobile)

    def audit(success: bool, reason: str = "", user: User | None = None):
        LoginAudit.objects.create(
            user=user, mobile=mobile.value, success=success,
            reason=reason, ip_address=ip, user_agent=user_agent[:400],
        )

    otp = (
        OtpRequest.objects.select_for_update()
        .filter(mobile=mobile.value, purpose=OtpRequest.PURPOSE_LOGIN, is_used=False)
        .order_by("-created_at")
        .first()
    )
    if not otp or not otp.is_valid:
        audit(False, "no_valid_otp")
        raise InvalidOtp("کدی معتبر یافت نشد یا منقضی شده است.")

    if not otp.check_code(code):
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        audit(False, "wrong_code")
        raise InvalidOtp("کد واردشده نادرست است.")

    otp.is_used = True
    otp.save(update_fields=["is_used"])

    # find or (optionally) create the user
    user = User.objects.filter(mobile=mobile.value).first()
    if user is None:
        if not settings.OTP_AUTO_CREATE_USER:
            audit(False, "unknown_user")
            raise UserNotAllowed("کاربری با این شماره در سامانه تعریف نشده است.")
        user = User.objects.create_user(mobile=mobile.value)

    if not user.is_active:
        audit(False, "inactive_user", user)
        raise UserNotAllowed("حساب کاربری غیرفعال است.")

    user.last_login_at = timezone.now()
    user.save(update_fields=["last_login_at"])
    audit(True, "ok", user)

    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": _user_brief(user),
    }


# --------------------------------------------------------------------------- #
# Queries
# --------------------------------------------------------------------------- #
def _user_brief(user: User) -> dict:
    return {
        "id": user.id,
        "mobile": user.mobile,
        "full_name": user.full_name,
        "is_super_admin": user.is_super_admin,
    }


def get_user_roles(user: User) -> dict:
    """Powers GET /me/roles — roles, scopes and the flattened permission set."""
    assignments = (
        UserRole.objects.filter(user=user, is_active=True)
        .select_related("role")
        .prefetch_related("role__permissions")
    )
    roles = []
    roles_with_perms = []
    for ur in assignments:
        perm_codes = list(ur.role.permissions.values_list("code", flat=True))
        roles.append({
            "code": ur.role.code,
            "name": ur.role.name,
            "scope_org_unit_id": ur.scope_org_unit_id,  # null = سراسری
        })
        roles_with_perms.append({"code": ur.role.code, "permissions": perm_codes})

    return {
        "user": _user_brief(user),
        "is_super_admin": user.is_super_admin,
        "roles": roles,
        "permissions": sorted(resolve_permissions(roles_with_perms)),
    }


# --------------------------------------------------------------------------- #
# Role management (used by the super-admin)
# --------------------------------------------------------------------------- #
@transaction.atomic
def assign_role(user: User, role_code: str, scope_org_unit_id: int | None = None) -> UserRole:
    role = Role.objects.get(code=role_code)
    ur, _ = UserRole.objects.get_or_create(
        user=user, role=role, scope_org_unit_id=scope_org_unit_id,
        defaults={"is_active": True},
    )
    return ur

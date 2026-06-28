"""DRF permission classes backed by the RBAC model."""
from rest_framework.permissions import BasePermission

from identity.application.services import get_user_roles


class IsSuperAdmin(BasePermission):
    message = "نیازمند دسترسی مدیر کل سامانه (Super Admin) است."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_super_admin)


class HasPermission(BasePermission):
    """
    Usage:
        permission_classes = [HasPermission.of("accommodation.complex.create")]
    Scope (org/province) enforcement happens later at the queryset/RLS level.
    """

    required_code: str = ""

    @classmethod
    def of(cls, code: str):
        return type(f"HasPermission_{code}", (cls,), {"required_code": code})

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_super_admin:
            return True
        return self.required_code in set(get_user_roles(user)["permissions"])


class HasAnyPermission(BasePermission):
    """Passes if the user has ANY of the given permission codes (or is super admin)."""

    required_codes: tuple = ()

    @classmethod
    def of(cls, *codes: str):
        return type(f"HasAnyPermission_{'_'.join(codes)}", (cls,), {"required_codes": tuple(codes)})

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_super_admin:
            return True
        return bool(set(self.required_codes) & set(get_user_roles(user)["permissions"]))

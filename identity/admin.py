from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from identity.models import (
    Dashboard,
    DashboardWidget,
    LoginAudit,
    OtpRequest,
    Permission,
    Role,
    User,
    UserRole,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("mobile",)
    list_display = ("mobile", "full_name", "is_active", "is_staff", "is_super_admin", "last_login_at")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("mobile", "full_name")
    readonly_fields = ("last_login_at", "date_joined", "last_login")
    fieldsets = (
        (None, {"fields": ("mobile", "password")}),
        ("اطلاعات", {"fields": ("full_name", "personnel_id")}),
        ("دسترسی‌ها", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("تاریخ‌ها", {"fields": ("last_login_at", "date_joined", "last_login")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("mobile", "full_name", "password1", "password2")}),
    )

    @admin.display(boolean=True, description="مدیر کل")
    def is_super_admin(self, obj):
        return obj.is_super_admin


class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 0
    autocomplete_fields = ("role",)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_system", "permission_count")
    search_fields = ("name", "code")
    filter_horizontal = ("permissions",)

    @admin.display(description="تعداد دسترسی")
    def permission_count(self, obj):
        return obj.permissions.count()


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "module")
    list_filter = ("module",)
    search_fields = ("code", "name")


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ("order", "title", "code", "group", "required_permission", "is_active")
    list_display_links = ("title",)
    list_editable = ("order", "is_active")
    list_filter = ("group", "is_active")
    search_fields = ("code", "title")
    autocomplete_fields = ("required_permission",)


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ("section", "order", "title", "widget_type", "data_key", "required_permission", "is_active")
    list_display_links = ("title",)
    list_editable = ("order", "is_active")
    list_filter = ("section", "widget_type", "is_active")
    search_fields = ("code", "title", "data_key")
    autocomplete_fields = ("required_permission",)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "scope_org_unit_id", "is_active")
    list_filter = ("is_active", "role")
    search_fields = ("user__mobile", "user__full_name")
    autocomplete_fields = ("user", "role")


@admin.register(LoginAudit)
class LoginAuditAdmin(admin.ModelAdmin):
    """RFP: who/when/what/IP — read-only login history."""

    list_display = ("created_at", "mobile", "success", "reason", "ip_address")
    list_filter = ("success", "created_at")
    search_fields = ("mobile", "ip_address")
    readonly_fields = [f.name for f in LoginAudit._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(OtpRequest)
class OtpRequestAdmin(admin.ModelAdmin):
    list_display = ("created_at", "mobile", "shown_code", "is_used", "attempts", "expires_at")
    list_filter = ("purpose", "is_used")
    search_fields = ("mobile",)
    readonly_fields = [f.name for f in OtpRequest._meta.fields]

    @admin.display(description="کد ورود")
    def shown_code(self, obj):
        # populated only in DEBUG; empty in production
        return obj.debug_code or "—"

    def has_add_permission(self, request):
        return False

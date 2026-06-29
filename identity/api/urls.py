from django.urls import include, path
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenRefreshView

from identity.api.views import (
    LoginAuditListView,
    MeView,
    MyDashboardSummaryView,
    MyDashboardView,
    MyDashboardsView,
    MyRolesView,
    OtpRequestView,
    OtpVerifyView,
    PermissionListView,
    RoleViewSet,
    UserAdminViewSet,
)

router = SimpleRouter(trailing_slash=False)
router.register("roles", RoleViewSet, basename="role")
router.register("admin/users", UserAdminViewSet, basename="admin-user")

urlpatterns = [
    # auth (OTP)
    path("auth/otp/request", OtpRequestView.as_view(), name="otp-request"),
    path("auth/otp/verify", OtpVerifyView.as_view(), name="otp-verify"),
    path("auth/token/refresh", TokenRefreshView.as_view(), name="token-refresh"),
    # current user
    path("me", MeView.as_view(), name="me"),
    path("me/roles", MyRolesView.as_view(), name="me-roles"),
    path("me/dashboards", MyDashboardsView.as_view(), name="me-dashboards"),  # sidebar menu
    path("me/dashboard", MyDashboardView.as_view(), name="me-dashboard"),  # home widgets
    path("me/dashboard/summary", MyDashboardSummaryView.as_view(), name="me-dashboard-summary"),
    # super-admin: roles + permissions catalog + audit
    path("permissions", PermissionListView.as_view(), name="permission-list"),
    path("admin/audit/logins", LoginAuditListView.as_view(), name="audit-logins"),
    path("", include(router.urls)),
]

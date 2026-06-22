from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from identity.api.views import (
    MeView,
    MyDashboardSummaryView,
    MyDashboardView,
    MyDashboardsView,
    MyRolesView,
    OtpRequestView,
    OtpVerifyView,
    PermissionListView,
    RoleViewSet,
)

router = DefaultRouter()
router.register("roles", RoleViewSet, basename="role")

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
    # super-admin: roles + permissions catalog
    path("permissions", PermissionListView.as_view(), name="permission-list"),
    path("", include(router.urls)),
]

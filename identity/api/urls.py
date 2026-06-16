from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from identity.api.views import (
    MeView,
    MyRolesView,
    OtpRequestView,
    OtpVerifyView,
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
    # super-admin role management
    path("", include(router.urls)),
]

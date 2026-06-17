from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from identity.application import services as app
from identity.domain.value_objects import InvalidMobileError
from identity.models import Role
from identity.api.permissions import IsSuperAdmin
from identity.api.serializers import OtpRequestSerializer, OtpVerifySerializer, RoleSerializer


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")


class OtpRequestView(APIView):
    """POST /api/v1/auth/otp/request — sends a one-time code."""

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        summary="درخواست کد ورود (OTP)",
        request=OtpRequestSerializer,
        responses={
            200: OpenApiResponse(description="کد ارسال شد"),
            400: OpenApiResponse(description="شماره موبایل نامعتبر"),
            429: OpenApiResponse(description="محدودیت نرخ درخواست"),
        },
    )
    def post(self, request):
        ser = OtpRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            result = app.request_otp(ser.validated_data["mobile"], ip=_client_ip(request))
        except InvalidMobileError:
            return Response({"detail": "شماره موبایل نامعتبر است."}, status=400)
        except app.TooManyRequests as e:
            return Response({"detail": str(e), "code": e.code}, status=429)
        return Response({"detail": "کد ارسال شد.", **result}, status=200)


class OtpVerifyView(APIView):
    """POST /api/v1/auth/otp/verify — verifies the code and returns JWT tokens."""

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        summary="تأیید کد و دریافت توکن JWT",
        request=OtpVerifySerializer,
        responses={
            200: OpenApiResponse(description="توکن صادر شد (access + refresh + user)"),
            400: OpenApiResponse(description="کد نادرست یا منقضی"),
            403: OpenApiResponse(description="کاربر تعریف‌نشده یا غیرفعال"),
        },
    )
    def post(self, request):
        ser = OtpVerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            result = app.verify_otp(
                ser.validated_data["mobile"],
                ser.validated_data["code"],
                ip=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except InvalidMobileError:
            return Response({"detail": "شماره موبایل نامعتبر است."}, status=400)
        except app.InvalidOtp as e:
            return Response({"detail": str(e), "code": e.code}, status=400)
        except app.UserNotAllowed as e:
            return Response({"detail": str(e), "code": e.code}, status=403)
        return Response(result, status=200)


class MeView(APIView):
    """GET /api/v1/me — current authenticated user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["me"], summary="کاربر جاری")
    def get(self, request):
        u = request.user
        return Response({
            "id": u.id,
            "mobile": u.mobile,
            "full_name": u.full_name,
            "is_super_admin": u.is_super_admin,
        })


class MyRolesView(APIView):
    """GET /api/v1/me/roles — roles + scopes + flattened permissions of the caller."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["me"], summary="نقش‌ها و دسترسی‌های کاربر جاری")
    def get(self, request):
        return Response(app.get_user_roles(request.user), status=status.HTTP_200_OK)


@extend_schema(tags=["roles"])
class RoleViewSet(viewsets.ModelViewSet):
    """Role management API (super-admin only). Mirrors the Django super-admin panel."""

    queryset = Role.objects.prefetch_related("permissions").all()
    serializer_class = RoleSerializer
    permission_classes = [IsSuperAdmin]
    lookup_field = "code"

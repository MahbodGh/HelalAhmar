from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from identity.application import services as app
from identity.domain.value_objects import InvalidMobileError
from identity.models import LoginAudit, Permission, Role, User
from identity.api.pagination import StandardPagination
from identity.api.permissions import HasPermission, IsSuperAdmin
from identity.api.serializers import (
    AssignRoleSerializer,
    DashboardSerializer,
    LoginAuditSerializer,
    OtpRequestSerializer,
    OtpVerifySerializer,
    PermissionSerializer,
    RoleSerializer,
    UserAdminSerializer,
    UserRoleSerializer,
)


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
        examples=[
            OpenApiExample("نمونه", value={"mobile": "09123456789"}, request_only=True),
        ],
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
        examples=[
            OpenApiExample(
                "نمونه", value={"mobile": "09123456789", "code": "123456"}, request_only=True
            ),
        ],
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


class MyDashboardsView(APIView):
    """GET /api/v1/me/dashboards — menu/dashboards the caller is allowed to see."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["me"],
        summary="داشبوردهای در دسترس کاربر جاری",
        responses=DashboardSerializer(many=True),
    )
    def get(self, request):
        dashboards = app.get_user_dashboards(request.user)
        return Response(DashboardSerializer(dashboards, many=True).data, status=status.HTTP_200_OK)


class MyDashboardView(APIView):
    """GET /api/v1/me/dashboard — composed home dashboard (widgets) for the caller."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["me"],
        summary="داشبورد خانهٔ کاربر جاری (ویجت‌ها بر اساس نقش)",
        responses={200: OpenApiResponse(description="sections → widgets")},
    )
    def get(self, request):
        return Response(app.get_user_dashboard(request.user), status=status.HTTP_200_OK)


class MyDashboardSummaryView(APIView):
    """GET /api/v1/me/dashboard/summary — stat values keyed by widget data_key."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["me"],
        summary="مقادیر آماری ویجت‌های داشبورد کاربر جاری",
        responses={200: OpenApiResponse(description="{ data_key: {value, status} }")},
    )
    def get(self, request):
        return Response(app.get_dashboard_summary(request.user), status=status.HTTP_200_OK)


@extend_schema(tags=["roles"], summary="فهرست همهٔ دسترسی‌ها (Super Admin)")
class PermissionListView(ListAPIView):
    """GET /api/v1/permissions — full permission catalog for the role-management UI."""

    queryset = Permission.objects.all().order_by("module", "code")
    serializer_class = PermissionSerializer
    permission_classes = [IsSuperAdmin]
    pagination_class = None


@extend_schema(tags=["roles"])
class RoleViewSet(viewsets.ModelViewSet):
    """Role management API (super-admin only). Mirrors the Django super-admin panel."""

    queryset = Role.objects.prefetch_related("permissions").all()
    serializer_class = RoleSerializer
    permission_classes = [IsSuperAdmin]
    lookup_field = "code"


@extend_schema(tags=["admin-users"])
class UserAdminViewSet(viewsets.ModelViewSet):
    """
    User & access management (super_admin / identity.user.manage).
    list / retrieve / create / partial_update — no hard delete (use is_active).
    """

    queryset = User.objects.all().order_by("-date_joined").prefetch_related("user_roles__role")
    serializer_class = UserAdminSerializer
    permission_classes = [HasPermission.of("identity.user.manage")]
    pagination_class = StandardPagination
    http_method_names = ["get", "post", "patch", "head", "options"]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["mobile", "full_name"]
    ordering_fields = ["date_joined", "last_login_at", "mobile"]

    def get_queryset(self):
        qs = super().get_queryset()
        is_active = self.request.query_params.get("is_active")
        if is_active in ("true", "false"):
            qs = qs.filter(is_active=(is_active == "true"))
        return qs

    @extend_schema(
        methods=["GET"], responses=UserRoleSerializer(many=True),
        summary="فهرست نقش‌های یک کاربر",
    )
    @extend_schema(
        methods=["POST"], request=AssignRoleSerializer, responses=UserRoleSerializer,
        summary="انتساب نقش به کاربر",
    )
    @action(detail=True, methods=["get", "post"], url_path="roles")
    def roles(self, request, pk=None):
        user = self.get_object()
        if request.method == "POST":
            ser = AssignRoleSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ur = app.assign_role(
                user,
                ser.validated_data["role_code"],
                ser.validated_data.get("scope_org_unit_id"),
            )
            return Response(UserRoleSerializer(ur).data, status=status.HTTP_201_CREATED)
        qs = user.user_roles.select_related("role").all()
        return Response(UserRoleSerializer(qs, many=True).data)

    @extend_schema(
        request={"application/json": {"type": "object", "properties": {"user_role_id": {"type": "integer"}}}},
        responses={204: OpenApiResponse(description="حذف شد")},
        summary="حذف یک انتساب نقش از کاربر",
    )
    @action(detail=True, methods=["post"], url_path="revoke-role")
    def revoke_role(self, request, pk=None):
        user = self.get_object()
        app.revoke_role(user, request.data.get("user_role_id"))
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["admin-users"], summary="لاگ‌های ورود (identity.audit.view)")
class LoginAuditListView(ListAPIView):
    """GET /api/v1/admin/audit/logins — login history with filters."""

    queryset = LoginAudit.objects.select_related("user").order_by("-created_at")
    serializer_class = LoginAuditSerializer
    permission_classes = [HasPermission.of("identity.audit.view")]
    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ["mobile", "ip_address"]

    def get_queryset(self):
        qs = super().get_queryset()
        success = self.request.query_params.get("success")
        if success in ("true", "false"):
            qs = qs.filter(success=(success == "true"))
        return qs

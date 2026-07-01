from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from identity.api.pagination import StandardPagination
from identity.api.permissions import HasPermission
from loan.api.serializers import (
    ApproveLoanSerializer,
    CreateLoanRequestSerializer,
    LoanRequestSerializer,
    LoanTypeSerializer,
    ReviewSerializer,
)
from loan.application import services as app
from loan.models import LoanType

MANAGE = "loan.request.manage"


@extend_schema(tags=["loan-types"])
class LoanTypeViewSet(viewsets.ModelViewSet):
    """انواع وام. نوشتن: loan.request.manage · خواندن: هر کاربر واردشده."""

    queryset = LoanType.objects.all()
    serializer_class = LoanTypeSerializer
    pagination_class = StandardPagination
    ordering = ["name"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [HasPermission.of(MANAGE)()]

    def get_queryset(self):
        qs = LoanType.objects.all()
        if self.request.query_params.get("active") == "1":
            qs = qs.filter(is_active=True)
        return qs


@extend_schema(tags=["loan-requests"])
class LoanRequestViewSet(viewsets.ModelViewSet):
    """درخواست‌های وام. ساخت: کارمند · بررسی/پرداخت: loan.request.manage."""

    serializer_class = LoanRequestSerializer
    pagination_class = StandardPagination
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action in ("approve", "reject", "disburse"):
            return [HasPermission.of(MANAGE)()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = app.scoped_requests(self.request.user)
        params = self.request.query_params
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("loan_type"):
            qs = qs.filter(loan_type_id=params["loan_type"])
        return qs

    def create(self, request, *args, **kwargs):
        ser = CreateLoanRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        personnel = None
        if d.get("personnel"):
            from hr.models import Personnel
            personnel = Personnel.objects.filter(id=d["personnel"]).first()
        try:
            req = app.create_request(
                user=request.user, loan_type=d["loan_type"], requested_amount=d["requested_amount"],
                installments_count=d["installments_count"], reason=d.get("reason", ""), personnel=personnel,
            )
        except app.LoanError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(LoanRequestSerializer(req).data, status=status.HTTP_201_CREATED)

    def _is_owner_or_manager(self, req, user):
        return user.is_super_admin or MANAGE in app._user_perms(user) or req.personnel_id == user.personnel_id

    @extend_schema(responses=LoanRequestSerializer, summary="لغو درخواست (صاحب)")
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        req = self.get_object()
        if not self._is_owner_or_manager(req, request.user):
            return Response(status=403)
        try:
            app.cancel_request(req)
        except app.LoanError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(LoanRequestSerializer(req).data)

    @extend_schema(request=ApproveLoanSerializer, responses=LoanRequestSerializer, summary="تأیید وام (کارشناس)")
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        req = self.get_object()
        ser = ApproveLoanSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            app.approve_request(req, request.user, ser.validated_data.get("approved_amount"), ser.validated_data.get("note", ""))
        except app.LoanError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(LoanRequestSerializer(req).data)

    @extend_schema(request=ReviewSerializer, responses=LoanRequestSerializer, summary="رد وام (کارشناس)")
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        req = self.get_object()
        ser = ReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            app.reject_request(req, request.user, ser.validated_data.get("note", ""))
        except app.LoanError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(LoanRequestSerializer(req).data)

    @extend_schema(responses=LoanRequestSerializer, summary="ثبت پرداخت وام (کارشناس/مالی)")
    @action(detail=True, methods=["post"], url_path="disburse")
    def disburse(self, request, pk=None):
        req = self.get_object()
        try:
            app.disburse_request(req)
        except app.LoanError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(LoanRequestSerializer(req).data)

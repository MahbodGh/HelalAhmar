from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from identity.api.pagination import StandardPagination
from identity.api.permissions import HasPermission
from insurance.application import services as app
from insurance.api.serializers import (
    CreateInsuranceRequestSerializer,
    InsurancePlanSerializer,
    InsuranceRequestSerializer,
    ReviewSerializer,
)
from insurance.models import InsurancePlan

MANAGE = "insurance.request.manage"


@extend_schema(tags=["insurance-plans"])
class InsurancePlanViewSet(viewsets.ModelViewSet):
    """طرح‌های بیمه. نوشتن: insurance.request.manage · خواندن: هر کاربر واردشده."""

    queryset = InsurancePlan.objects.all()
    serializer_class = InsurancePlanSerializer
    pagination_class = StandardPagination
    ordering = ["name"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [HasPermission.of(MANAGE)()]

    def get_queryset(self):
        qs = InsurancePlan.objects.all()
        if self.request.query_params.get("active") == "1":
            qs = qs.filter(is_active=True)
        return qs


@extend_schema(tags=["insurance-requests"])
class InsuranceRequestViewSet(viewsets.ModelViewSet):
    """درخواست‌های بیمه. ساخت: هر کارمندِ دارای پرسنل · بررسی: insurance.request.manage."""

    serializer_class = InsuranceRequestSerializer
    pagination_class = StandardPagination
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action in ("approve", "reject"):
            return [HasPermission.of(MANAGE)()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = app.scoped_requests(self.request.user)
        if self.request.query_params.get("status"):
            qs = qs.filter(status=self.request.query_params["status"])
        return qs

    def create(self, request, *args, **kwargs):
        ser = CreateInsuranceRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        personnel = None
        if data.get("personnel"):
            from hr.models import Personnel
            personnel = Personnel.objects.filter(id=data["personnel"]).first()
        try:
            req = app.create_request(
                user=request.user, plan=data["plan"], dependent_ids=data.get("dependent_ids"),
                coverage_start=data.get("coverage_start"), coverage_end=data.get("coverage_end"),
                personnel=personnel,
            )
        except app.InsuranceError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(InsuranceRequestSerializer(req).data, status=status.HTTP_201_CREATED)

    def _is_owner_or_manager(self, req, user):
        return user.is_super_admin or MANAGE in app._user_perms(user) or req.personnel_id == user.personnel_id

    @extend_schema(responses=InsuranceRequestSerializer, summary="لغو درخواست (صاحب درخواست)")
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        req = self.get_object()
        if not self._is_owner_or_manager(req, request.user):
            return Response(status=403)
        try:
            app.cancel_request(req)
        except app.InsuranceError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(InsuranceRequestSerializer(req).data)

    @extend_schema(request=ReviewSerializer, responses=InsuranceRequestSerializer, summary="تأیید درخواست (کارشناس)")
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        req = self.get_object()
        ser = ReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            app.approve_request(req, request.user, ser.validated_data.get("note", ""))
        except app.InsuranceError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(InsuranceRequestSerializer(req).data)

    @extend_schema(request=ReviewSerializer, responses=InsuranceRequestSerializer, summary="رد درخواست (کارشناس)")
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        req = self.get_object()
        ser = ReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            app.reject_request(req, request.user, ser.validated_data.get("note", ""))
        except app.InsuranceError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(InsuranceRequestSerializer(req).data)


from insurance.api.serializers import (  # noqa: E402
    ApproveClaimSerializer,
    CreateClaimSerializer,
    InsuranceClaimSerializer,
)


@extend_schema(tags=["insurance-claims"])
class InsuranceClaimViewSet(viewsets.ModelViewSet):
    """درخواست‌های خسارت. ثبت: بیمه‌شده · بررسی/پرداخت: insurance.request.manage."""

    serializer_class = InsuranceClaimSerializer
    pagination_class = StandardPagination
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action in ("approve", "reject", "mark_paid"):
            return [HasPermission.of(MANAGE)()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = app.scoped_claims(self.request.user)
        params = self.request.query_params
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("request"):
            qs = qs.filter(request_id=params["request"])
        return qs

    def create(self, request, *args, **kwargs):
        ser = CreateClaimSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            claim = app.create_claim(
                user=request.user, request=d["request"], service_type=d["service_type"],
                claimed_amount=d["claimed_amount"], service_date=d.get("service_date"),
                patient_dependent_id=d.get("patient_dependent_id"),
                description=d.get("description", ""), documents=d.get("documents", []),
            )
        except app.InsuranceError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(InsuranceClaimSerializer(claim).data, status=status.HTTP_201_CREATED)

    def _is_owner_or_manager(self, claim, user):
        return user.is_super_admin or MANAGE in app._user_perms(user) or claim.personnel_id == user.personnel_id

    @extend_schema(responses=InsuranceClaimSerializer, summary="لغو خسارت (صاحب)")
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        claim = self.get_object()
        if not self._is_owner_or_manager(claim, request.user):
            return Response(status=403)
        try:
            app.cancel_claim(claim)
        except app.InsuranceError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(InsuranceClaimSerializer(claim).data)

    @extend_schema(request=ApproveClaimSerializer, responses=InsuranceClaimSerializer, summary="تأیید خسارت (کارشناس)")
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        claim = self.get_object()
        ser = ApproveClaimSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            app.approve_claim(claim, request.user, ser.validated_data["approved_amount"], ser.validated_data.get("note", ""))
        except app.InsuranceError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(InsuranceClaimSerializer(claim).data)

    @extend_schema(request=ReviewSerializer, responses=InsuranceClaimSerializer, summary="رد خسارت (کارشناس)")
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        claim = self.get_object()
        ser = ReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            app.reject_claim(claim, request.user, ser.validated_data.get("note", ""))
        except app.InsuranceError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(InsuranceClaimSerializer(claim).data)

    @extend_schema(responses=InsuranceClaimSerializer, summary="ثبت پرداخت خسارت (کارشناس/مالی)")
    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request, pk=None):
        claim = self.get_object()
        try:
            app.mark_claim_paid(claim)
        except app.InsuranceError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(InsuranceClaimSerializer(claim).data)

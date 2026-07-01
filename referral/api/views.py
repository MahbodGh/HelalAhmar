from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from identity.api.pagination import StandardPagination
from identity.api.permissions import HasPermission
from referral.application import services as app
from referral.api.serializers import (
    ContractedProviderSerializer,
    CreateReferralLetterSerializer,
    IssueLetterSerializer,
    ReferralLetterSerializer,
    ReviewSerializer,
)
from referral.models import ContractedProvider

MANAGE = "referral.letter.manage"


@extend_schema(tags=["referral-providers"])
class ContractedProviderViewSet(viewsets.ModelViewSet):
    """مراکز طرف‌قرارداد. نوشتن: referral.letter.manage · خواندن: هر کاربر واردشده."""

    queryset = ContractedProvider.objects.all()
    serializer_class = ContractedProviderSerializer
    pagination_class = StandardPagination
    ordering = ["name"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [HasPermission.of(MANAGE)()]

    def get_queryset(self):
        qs = ContractedProvider.objects.all()
        params = self.request.query_params
        if params.get("active") == "1":
            qs = qs.filter(is_active=True)
        if params.get("category"):
            qs = qs.filter(category=params["category"])
        return qs


@extend_schema(tags=["referral-letters"])
class ReferralLetterViewSet(viewsets.ModelViewSet):
    """معرفی‌نامه‌ها. ثبت درخواست: هر کارمند · صدور/رد: referral.letter.manage."""

    serializer_class = ReferralLetterSerializer
    pagination_class = StandardPagination
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action in ("issue", "reject", "mark_used"):
            return [HasPermission.of(MANAGE)()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = app.scoped_letters(self.request.user)
        params = self.request.query_params
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("provider"):
            qs = qs.filter(provider_id=params["provider"])
        return qs

    def create(self, request, *args, **kwargs):
        ser = CreateReferralLetterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        personnel = None
        if d.get("personnel"):
            from hr.models import Personnel
            personnel = Personnel.objects.filter(id=d["personnel"]).first()
        try:
            letter = app.create_letter(
                user=request.user, provider=d["provider"], service_description=d["service_description"],
                beneficiary_dependent_id=d.get("beneficiary_dependent_id"), note=d.get("note", ""),
                personnel=personnel,
            )
        except app.ReferralError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ReferralLetterSerializer(letter).data, status=status.HTTP_201_CREATED)

    def _is_owner_or_manager(self, letter, user):
        return user.is_super_admin or MANAGE in app._user_perms(user) or letter.personnel_id == user.personnel_id

    @extend_schema(responses=ReferralLetterSerializer, summary="لغو معرفی‌نامه (صاحب)")
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        letter = self.get_object()
        if not self._is_owner_or_manager(letter, request.user):
            return Response(status=403)
        try:
            app.cancel_letter(letter)
        except app.ReferralError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ReferralLetterSerializer(letter).data)

    @extend_schema(request=IssueLetterSerializer, responses=ReferralLetterSerializer, summary="صدور معرفی‌نامه (کارشناس)")
    @action(detail=True, methods=["post"], url_path="issue")
    def issue(self, request, pk=None):
        letter = self.get_object()
        ser = IssueLetterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            app.issue_letter(letter, request.user, ser.validated_data.get("valid_until"), ser.validated_data.get("note", ""))
        except app.ReferralError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ReferralLetterSerializer(letter).data)

    @extend_schema(request=ReviewSerializer, responses=ReferralLetterSerializer, summary="رد معرفی‌نامه (کارشناس)")
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        letter = self.get_object()
        ser = ReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            app.reject_letter(letter, request.user, ser.validated_data.get("note", ""))
        except app.ReferralError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ReferralLetterSerializer(letter).data)

    @extend_schema(responses=ReferralLetterSerializer, summary="ثبت استفاده (کارشناس)")
    @action(detail=True, methods=["post"], url_path="mark-used")
    def mark_used(self, request, pk=None):
        letter = self.get_object()
        try:
            app.mark_used(letter)
        except app.ReferralError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ReferralLetterSerializer(letter).data)

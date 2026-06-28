from django.db.models import Count
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from accommodation.application import services as app
from accommodation.models import (
    AccommodationComplex,
    AccommodationUnit,
    Amenity,
    SeasonalRate,
    UnitPlan,
)
from accommodation.api.serializers import (
    AmenitySerializer,
    ComplexDetailSerializer,
    ComplexListSerializer,
    SeasonalRateSerializer,
    UnitPlanSerializer,
    UnitSerializer,
    UnitStatusSerializer,
)
from identity.api.pagination import StandardPagination
from identity.api.permissions import HasAnyPermission, HasPermission

VIEW = "accommodation.complex.view"
MANAGE = "accommodation.complex.manage"
HK = "accommodation.housekeeping.manage"


def _rw_permissions(request):
    code = VIEW if request.method in ("GET", "HEAD", "OPTIONS") else MANAGE
    return [HasPermission.of(code)()]


@extend_schema(tags=["accommodation-base"])
class AmenityViewSet(viewsets.ModelViewSet):
    queryset = Amenity.objects.all()
    serializer_class = AmenitySerializer
    pagination_class = None
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def get_permissions(self):
        return _rw_permissions(self.request)


@extend_schema(tags=["accommodation-base"])
class UnitPlanViewSet(viewsets.ModelViewSet):
    queryset = UnitPlan.objects.all()
    serializer_class = UnitPlanSerializer
    pagination_class = None

    def get_permissions(self):
        return _rw_permissions(self.request)


@extend_schema(tags=["accommodation-complexes"])
class ComplexViewSet(viewsets.ModelViewSet):
    """مجموعه‌های اقامتی (RLS-اسکوپ). Read: complex.view · Write: complex.manage."""

    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "code", "address"]
    ordering_fields = ["name"]

    def get_permissions(self):
        return _rw_permissions(self.request)

    def get_serializer_class(self):
        return ComplexListSerializer if self.action == "list" else ComplexDetailSerializer

    def get_queryset(self):
        qs = app.scoped_complex_qs(self.request.user)
        params = self.request.query_params
        if params.get("province"):
            qs = qs.filter(province_id=params["province"])
        if params.get("is_active") in ("true", "false"):
            qs = qs.filter(is_active=(params["is_active"] == "true"))
        if self.action == "list":
            qs = qs.annotate(units_count=Count("units"))
        return qs

    @extend_schema(responses=UnitSerializer(many=True), summary="واحدهای یک مجموعه")
    @action(detail=True, methods=["get"], url_path="units")
    def units(self, request, pk=None):
        complex_obj = self.get_object()
        qs = complex_obj.units.select_related("plan").all()
        return Response(UnitSerializer(qs, many=True).data)

    @extend_schema(
        summary="پلان مجموعه — وضعیت لحظه‌ای واحدها",
        responses={200: OpenApiResponse(description="واحدها با وضعیت برای نمایش گرافیکی")},
    )
    @action(detail=True, methods=["get"], url_path="plan")
    def plan(self, request, pk=None):
        complex_obj = self.get_object()
        units = complex_obj.units.select_related("plan").all()
        summary: dict = {}
        for u in units:
            summary[u.status] = summary.get(u.status, 0) + 1
        return Response({
            "complex": {"id": complex_obj.id, "name": complex_obj.name},
            "status_summary": summary,
            "units": UnitSerializer(units, many=True).data,
        })


@extend_schema(tags=["accommodation-units"])
class UnitViewSet(viewsets.ModelViewSet):
    """واحدهای اقامتی (RLS-اسکوپ از طریق مجموعه)."""

    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ["name_or_number"]

    def get_permissions(self):
        if self.action in ("set_status", "mark_cleaned"):
            return [HasAnyPermission.of(MANAGE, "accommodation.checkin.manage", HK)()]
        return _rw_permissions(self.request)

    def get_serializer_class(self):
        return UnitStatusSerializer if self.action == "set_status" else UnitSerializer

    def get_queryset(self):
        qs = app.scoped_unit_qs(self.request.user)
        params = self.request.query_params
        if params.get("complex"):
            qs = qs.filter(complex_id=params["complex"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        return qs

    @extend_schema(request=UnitStatusSerializer, responses=UnitSerializer, summary="تغییر وضعیت واحد")
    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, pk=None):
        unit = self.get_object()
        ser = UnitStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        unit.status = ser.validated_data["status"]
        unit.save(update_fields=["status"])
        return Response(UnitSerializer(unit).data)

    @extend_schema(responses=UnitSerializer, summary="ثبت اتمام نظافت (وضعیت → فعال)")
    @action(detail=True, methods=["post"], url_path="mark-cleaned")
    def mark_cleaned(self, request, pk=None):
        unit = self.get_object()
        unit.status = AccommodationUnit.STATUS_ACTIVE
        unit.save(update_fields=["status"])
        return Response(UnitSerializer(unit).data)

    @extend_schema(methods=["GET"], responses=SeasonalRateSerializer(many=True))
    @extend_schema(methods=["POST"], request=SeasonalRateSerializer, responses=SeasonalRateSerializer)
    @action(detail=True, methods=["get", "post"], url_path="rates")
    def rates(self, request, pk=None):
        unit = self.get_object()
        if request.method == "POST":
            data = {**request.data, "unit": unit.id}
            ser = SeasonalRateSerializer(data=data)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        return Response(SeasonalRateSerializer(unit.rates.all(), many=True).data)


@extend_schema(tags=["accommodation-units"], summary="صف نظافت (واحدهای در حال نظافت)")
class HousekeepingQueueView(ListAPIView):
    serializer_class = UnitSerializer
    pagination_class = None
    permission_classes = [HasPermission.of(HK)]

    def get_queryset(self):
        return app.scoped_unit_qs(self.request.user).filter(
            status=AccommodationUnit.STATUS_CLEANING
        )

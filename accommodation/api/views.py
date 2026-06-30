from django.db.models import Count
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from accommodation.application import services as app
from accommodation.models import (
    AccommodationComplex,
    AccommodationUnit,
    Amenity,
    Reservation,
    ReservationPeriod,
    SeasonalRate,
    UnitPlan,
)
from accommodation.api.serializers import (
    AmenitySerializer,
    ComplexDetailSerializer,
    ComplexListSerializer,
    CreateReservationSerializer,
    EnrollLotterySerializer,
    LotteryEnrollmentSerializer,
    LotteryRunSerializer,
    ReservationPeriodSerializer,
    ReservationSerializer,
    RunLotterySerializer,
    SeasonalRateSerializer,
    UnitPlanSerializer,
    UnitSerializer,
    UnitStatusSerializer,
    VerifyVoucherSerializer,
    VoucherSerializer,
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
            qs = qs.annotate(units_count=Count("units")).order_by("name")
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


RES_MANAGE = "accommodation.reservation.manage"
RES_CREATE = "accommodation.reservation.create"
from rest_framework.permissions import IsAuthenticated  # noqa: E402


@extend_schema(tags=["accommodation-periods"])
class ReservationPeriodViewSet(viewsets.ModelViewSet):
    """دوره‌های رزرو. CRUD: reservation.manage · مشاهدهٔ دوره‌های فعال: هر کاربر واردشده."""

    queryset = ReservationPeriod.objects.prefetch_related("units").all()
    serializer_class = ReservationPeriodSerializer
    pagination_class = StandardPagination

    def get_permissions(self):
        if self.action == "enroll":
            return [HasPermission.of(RES_CREATE)()]
        if self.action in ("active", "available_units", "my_enrollment"):
            return [IsAuthenticated()]
        return [HasPermission.of(RES_MANAGE)()]

    @extend_schema(responses=ReservationPeriodSerializer(many=True), summary="دوره‌های فعالِ قابل‌رزرو برای کاربر جاری")
    @action(detail=False, methods=["get"], url_path="active")
    def active(self, request):
        periods = app.active_periods_for(request.user)
        return Response(ReservationPeriodSerializer(periods, many=True).data)

    @extend_schema(
        summary="واحدهای خالی یک دوره برای بازهٔ انتخابی",
        responses=UnitSerializer(many=True),
    )
    @action(detail=True, methods=["get"], url_path="available-units")
    def available_units(self, request, pk=None):
        period = self.get_object()
        from datetime import date as _date

        try:
            check_in = _date.fromisoformat(request.query_params["check_in"])
            check_out = _date.fromisoformat(request.query_params["check_out"])
            persons = int(request.query_params.get("persons", "1"))
        except (KeyError, ValueError):
            return Response({"detail": "پارامترهای check_in/check_out/persons نامعتبرند."}, status=400)
        units = app.available_units(period, check_in, check_out, persons)
        return Response(UnitSerializer(units, many=True).data)

    @extend_schema(request=EnrollLotterySerializer, responses=LotteryEnrollmentSerializer, summary="ثبت‌نام در قرعه‌کشی")
    @action(detail=True, methods=["post"], url_path="enroll")
    def enroll(self, request, pk=None):
        period = self.get_object()
        ser = EnrollLotterySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        personnel = None
        if data.get("personnel"):
            from hr.models import Personnel
            personnel = Personnel.objects.filter(id=data["personnel"]).first()
        try:
            enrollment = app.enroll_lottery(
                user=request.user, period=period,
                first_degree=data["first_degree_companions"], other=data["other_companions"],
                preferred_unit_ids=data.get("preferred_units") or None, personnel=personnel,
            )
        except app.ReservationError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(LotteryEnrollmentSerializer(enrollment).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=LotteryEnrollmentSerializer, summary="ثبت‌نام قرعه‌کشیِ کاربر جاری در این دوره")
    @action(detail=True, methods=["get"], url_path="my-enrollment")
    def my_enrollment(self, request, pk=None):
        period = self.get_object()
        e = LotteryEnrollment.objects.filter(period=period, personnel_id=request.user.personnel_id).first()
        if not e:
            return Response({"detail": "ثبت‌نامی یافت نشد."}, status=404)
        return Response(LotteryEnrollmentSerializer(e).data)

    @extend_schema(
        request=RunLotterySerializer,
        responses={200: OpenApiResponse(description="{run_id, total_enrollments, winners, losers}")},
        summary="اجرای قرعه‌کشی دوره (reservation.manage)",
    )
    @action(detail=True, methods=["post"], url_path="run-lottery")
    def run_lottery(self, request, pk=None):
        period = self.get_object()
        ser = RunLotterySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        seed = ser.validated_data.get("seed") or None
        try:
            result = app.run_lottery(period=period, run_by=request.user, seed=seed)
        except app.ReservationError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(result)

    @extend_schema(responses=LotteryEnrollmentSerializer(many=True), summary="ثبت‌نام‌های قرعه‌کشی دوره (reservation.manage)")
    @action(detail=True, methods=["get"], url_path="enrollments")
    def enrollments(self, request, pk=None):
        period = self.get_object()
        qs = app.scoped_enrollments(request.user, period=period)
        return Response(LotteryEnrollmentSerializer(qs, many=True).data)


@extend_schema(tags=["accommodation-reservations"])
class ReservationViewSet(viewsets.ModelViewSet):
    """رزروها. ساخت: reservation.create · فهرست: مال خود (یا اسکوپ برای مدیر)."""

    serializer_class = ReservationSerializer
    pagination_class = StandardPagination
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action == "create":
            return [HasPermission.of(RES_CREATE)()]
        if self.action in ("check_in", "check_out", "verify_voucher"):
            return [HasPermission.of("accommodation.checkin.manage")()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = app.scoped_reservations(self.request.user)
        params = self.request.query_params
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        return qs

    def create(self, request, *args, **kwargs):
        ser = CreateReservationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        personnel = None
        if data.get("personnel"):
            from hr.models import Personnel
            personnel = Personnel.objects.filter(id=data["personnel"]).first()
        try:
            res = app.create_reservation(
                user=request.user, period=data["period"], unit=data["unit"],
                check_in=data["check_in_date"], check_out=data["check_out_date"],
                first_degree=data["first_degree_companions"], other=data["other_companions"],
                payment_method=data.get("payment_method", ""), personnel=personnel,
            )
        except app.UnitUnavailableError as e:
            return Response({"detail": str(e)}, status=409)
        except app.ReservationError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ReservationSerializer(res).data, status=status.HTTP_201_CREATED)

    def _owned_or_manager(self, reservation, user):
        return (
            user.is_super_admin
            or "accommodation.reservation.manage" in app._user_perms(user)
            or reservation.personnel_id == user.personnel_id
        )

    @extend_schema(responses=ReservationSerializer, summary="پرداخت/تأیید رزرو")
    @action(detail=True, methods=["post"], url_path="pay")
    def pay(self, request, pk=None):
        res = self.get_object()
        if not self._owned_or_manager(res, request.user):
            return Response(status=403)
        try:
            app.pay_reservation(res)
        except app.ReservationError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ReservationSerializer(res).data)

    @extend_schema(responses=ReservationSerializer, summary="لغو رزرو")
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        res = self.get_object()
        if not self._owned_or_manager(res, request.user):
            return Response(status=403)
        try:
            app.cancel_reservation(res)
        except app.ReservationError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ReservationSerializer(res).data)

    @extend_schema(responses=VoucherSerializer, summary="ووچر QR رزرو (تأییدشده)")
    @action(detail=True, methods=["get"], url_path="voucher")
    def voucher(self, request, pk=None):
        res = self.get_object()
        if not self._owned_or_manager(res, request.user):
            return Response(status=403)
        if res.status not in (Reservation.CONFIRMED, Reservation.CHECKED_IN, Reservation.CHECKED_OUT):
            return Response({"detail": "ووچر فقط برای رزرو تأییدشده در دسترس است."}, status=400)
        v = app.issue_voucher(res)
        return Response(VoucherSerializer(v).data)

    @extend_schema(request=VerifyVoucherSerializer, responses=ReservationSerializer,
                   summary="اسکن/استعلام ووچر (پذیرش)")
    @action(detail=False, methods=["post"], url_path="verify-voucher")
    def verify_voucher(self, request):
        ser = VerifyVoucherSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        res = app.find_reservation_by_voucher(ser.validated_data["token"])
        if res is None:
            return Response({"detail": "ووچر نامعتبر است."}, status=404)
        return Response(ReservationSerializer(res).data)

    @extend_schema(responses=ReservationSerializer, summary="ثبت ورود (پذیرش)")
    @action(detail=True, methods=["post"], url_path="check-in")
    def check_in(self, request, pk=None):
        res = self.get_object()
        try:
            app.check_in(res, request.user)
        except app.ReservationError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ReservationSerializer(res).data)

    @extend_schema(responses=ReservationSerializer, summary="ثبت خروج (واحد به صف نظافت می‌رود)")
    @action(detail=True, methods=["post"], url_path="check-out")
    def check_out(self, request, pk=None):
        res = self.get_object()
        try:
            app.check_out(res, request.user)
        except app.ReservationError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ReservationSerializer(res).data)


# --------------------------------------------------------------------------- #
# BI / analytics endpoints (slice 5) — RLS-scoped, gated by accommodation.bi.view
# --------------------------------------------------------------------------- #
BI = "accommodation.bi.view"


@extend_schema(tags=["accommodation-bi"], summary="خلاصهٔ شاخص‌های اقامت (RLS)")
class BISummaryView(APIView):
    permission_classes = [HasPermission.of(BI)]

    def get(self, request):
        return Response(app.bi_summary(request.user))


@extend_schema(tags=["accommodation-bi"], summary="روند رزرو ماهانه")
class BITrendView(APIView):
    permission_classes = [HasPermission.of(BI)]

    def get(self, request):
        try:
            months = int(request.query_params.get("months", "6"))
        except ValueError:
            months = 6
        return Response(app.bi_reservation_trend(request.user, months))


@extend_schema(tags=["accommodation-bi"], summary="رزرو به تفکیک استان")
class BIProvinceView(APIView):
    permission_classes = [HasPermission.of(BI)]

    def get(self, request):
        return Response(app.bi_occupancy_by_province(request.user))


@extend_schema(tags=["accommodation-bi"], summary="محبوب‌ترین مراکز")
class BIPopularView(APIView):
    permission_classes = [HasPermission.of(BI)]

    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", "10"))
        except ValueError:
            limit = 10
        return Response(app.bi_popular_centers(request.user, limit))


@extend_schema(tags=["accommodation-bi"], summary="تفکیک وضعیت واحدها و رزروها")
class BIStatusView(APIView):
    permission_classes = [HasPermission.of(BI)]

    def get(self, request):
        return Response(app.bi_status_breakdown(request.user))

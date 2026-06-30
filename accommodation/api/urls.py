from django.urls import include, path
from rest_framework.routers import SimpleRouter

from accommodation.api.views import (
    AmenityViewSet,
    BIPopularView,
    BIProvinceView,
    BIStatusView,
    BISummaryView,
    BITrendView,
    ComplexViewSet,
    HousekeepingQueueView,
    ReservationPeriodViewSet,
    ReservationViewSet,
    UnitPlanViewSet,
    UnitViewSet,
)

router = SimpleRouter(trailing_slash=False)
router.register("accommodation/amenities", AmenityViewSet, basename="amenity")
router.register("accommodation/plans", UnitPlanViewSet, basename="unit-plan")
router.register("accommodation/complexes", ComplexViewSet, basename="complex")
router.register("accommodation/units", UnitViewSet, basename="unit")
router.register("accommodation/periods", ReservationPeriodViewSet, basename="reservation-period")
router.register("accommodation/reservations", ReservationViewSet, basename="reservation")

urlpatterns = [
    path("accommodation/housekeeping/queue", HousekeepingQueueView.as_view(), name="housekeeping-queue"),
    path("accommodation/bi/summary", BISummaryView.as_view(), name="bi-summary"),
    path("accommodation/bi/reservation-trend", BITrendView.as_view(), name="bi-trend"),
    path("accommodation/bi/occupancy-by-province", BIProvinceView.as_view(), name="bi-province"),
    path("accommodation/bi/popular-centers", BIPopularView.as_view(), name="bi-popular"),
    path("accommodation/bi/status-breakdown", BIStatusView.as_view(), name="bi-status"),
    path("", include(router.urls)),
]

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from accommodation.api.views import (
    AmenityViewSet,
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
    path("", include(router.urls)),
]

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accommodation.api.views import (
    AmenityViewSet,
    ComplexViewSet,
    HousekeepingQueueView,
    UnitPlanViewSet,
    UnitViewSet,
)

router = DefaultRouter()
router.register("accommodation/amenities", AmenityViewSet, basename="amenity")
router.register("accommodation/plans", UnitPlanViewSet, basename="unit-plan")
router.register("accommodation/complexes", ComplexViewSet, basename="complex")
router.register("accommodation/units", UnitViewSet, basename="unit")

urlpatterns = [
    path("accommodation/housekeeping/queue", HousekeepingQueueView.as_view(), name="housekeeping-queue"),
    path("", include(router.urls)),
]

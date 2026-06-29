from django.urls import include, path
from rest_framework.routers import SimpleRouter

from hr.api.views import (
    CityListView,
    DependentViewSet,
    OrgUnitViewSet,
    PersonnelViewSet,
    ProvinceListView,
)

router = SimpleRouter(trailing_slash=False)
router.register("hr/org-units", OrgUnitViewSet, basename="org-unit")
router.register("hr/personnel", PersonnelViewSet, basename="personnel")
router.register("hr/dependents", DependentViewSet, basename="dependent")

urlpatterns = [
    path("hr/provinces", ProvinceListView.as_view(), name="province-list"),
    path("hr/cities", CityListView.as_view(), name="city-list"),
    path("", include(router.urls)),
]

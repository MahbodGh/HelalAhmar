from django.urls import include, path
from rest_framework.routers import SimpleRouter

from insurance.api.views import (
    InsuranceClaimViewSet,
    InsurancePlanViewSet,
    InsuranceRequestViewSet,
)

router = SimpleRouter(trailing_slash=False)
router.register("insurance/plans", InsurancePlanViewSet, basename="insurance-plan")
router.register("insurance/requests", InsuranceRequestViewSet, basename="insurance-request")
router.register("insurance/claims", InsuranceClaimViewSet, basename="insurance-claim")

urlpatterns = [
    path("", include(router.urls)),
]

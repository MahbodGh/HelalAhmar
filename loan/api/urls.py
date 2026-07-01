from django.urls import include, path
from rest_framework.routers import SimpleRouter

from loan.api.views import LoanRequestViewSet, LoanTypeViewSet

router = SimpleRouter(trailing_slash=False)
router.register("loan/types", LoanTypeViewSet, basename="loan-type")
router.register("loan/requests", LoanRequestViewSet, basename="loan-request")

urlpatterns = [
    path("", include(router.urls)),
]

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from finance.api.views import DeductionBatchViewSet

router = SimpleRouter(trailing_slash=False)
router.register("finance/batches", DeductionBatchViewSet, basename="deduction-batch")

urlpatterns = [
    path("", include(router.urls)),
]

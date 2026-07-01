from django.urls import include, path
from rest_framework.routers import SimpleRouter

from referral.api.views import ContractedProviderViewSet, ReferralLetterViewSet

router = SimpleRouter(trailing_slash=False)
router.register("referral/providers", ContractedProviderViewSet, basename="referral-provider")
router.register("referral/letters", ReferralLetterViewSet, basename="referral-letter")

urlpatterns = [
    path("", include(router.urls)),
]

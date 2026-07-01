from django.urls import include, path
from rest_framework.routers import SimpleRouter

from welfare.api.views import MyWelfareProfileView, WelfareNoteViewSet, WelfareProfileView

router = SimpleRouter(trailing_slash=False)
router.register("welfare/notes", WelfareNoteViewSet, basename="welfare-note")

urlpatterns = [
    path("welfare/profile/me", MyWelfareProfileView.as_view(), name="welfare-profile-me"),
    path("welfare/profile/<int:personnel_id>", WelfareProfileView.as_view(), name="welfare-profile"),
    path("", include(router.urls)),
]

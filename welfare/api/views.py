from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from hr.models import Personnel
from identity.api.pagination import StandardPagination
from identity.api.permissions import HasPermission
from welfare.api.serializers import WelfareNoteSerializer
from welfare.application import services as app
from welfare.models import WelfareNote

VIEW = "welfare.profile.view"


@extend_schema(tags=["welfare-profile"], summary="پروندهٔ رفاهی خودم")
class MyWelfareProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.personnel_id:
            return Response({"detail": "به این کاربر پرسنلی متصل نیست."}, status=400)
        personnel = Personnel.objects.filter(id=request.user.personnel_id).first()
        if personnel is None:
            return Response({"detail": "پرسنل یافت نشد."}, status=404)
        return Response(app.build_profile(personnel, include_notes=False))


@extend_schema(tags=["welfare-profile"], summary="پروندهٔ رفاهی یک پرسنل (کارشناس رفاه)")
class WelfareProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, personnel_id):
        personnel = Personnel.objects.filter(id=personnel_id).first()
        if personnel is None:
            return Response({"detail": "پرسنل یافت نشد."}, status=404)
        if not app.can_view_personnel(request.user, personnel):
            return Response(status=403)
        # notes are visible only to staff viewing someone else's file
        include_notes = personnel.id != request.user.personnel_id
        return Response(app.build_profile(personnel, include_notes=include_notes))


@extend_schema(tags=["welfare-profile"])
class WelfareNoteViewSet(viewsets.ModelViewSet):
    """یادداشت‌های پروندهٔ رفاهی (کارشناس رفاه: welfare.profile.view)."""

    serializer_class = WelfareNoteSerializer
    pagination_class = StandardPagination
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_permissions(self):
        return [HasPermission.of(VIEW)()]

    def get_queryset(self):
        qs = app.scoped_notes(self.request.user)
        if self.request.query_params.get("personnel"):
            qs = qs.filter(personnel_id=self.request.query_params["personnel"])
        return qs

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

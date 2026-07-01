from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from identity.api.permissions import HasPermission
from report.application import services as app

VIEW = "report.dashboard.view"


@extend_schema(tags=["report"], summary="خلاصهٔ مدیریتی (کل خدمات، عدالت توزیع، هشدارها)")
class ReportSummaryView(APIView):
    permission_classes = [HasPermission.of(VIEW)]

    def get(self, request):
        return Response(app.summary(request.user))


@extend_schema(tags=["report"], summary="توزیع خدمات به تفکیک استان")
class ServicesByProvinceView(APIView):
    permission_classes = [HasPermission.of(VIEW)]

    def get(self, request):
        return Response(app.services_by_province(request.user))


@extend_schema(tags=["report"], summary="ماموریت‌های بحرانی (هشدارهای نیازمند اقدام)")
class CriticalMissionsView(APIView):
    permission_classes = [HasPermission.of(VIEW)]

    def get(self, request):
        return Response(app.critical_missions(request.user))

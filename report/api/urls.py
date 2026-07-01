from django.urls import path

from report.api.views import CriticalMissionsView, ReportSummaryView, ServicesByProvinceView

urlpatterns = [
    path("report/summary", ReportSummaryView.as_view(), name="report-summary"),
    path("report/services-by-province", ServicesByProvinceView.as_view(), name="report-services-by-province"),
    path("report/critical-missions", CriticalMissionsView.as_view(), name="report-critical-missions"),
]

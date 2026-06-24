from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

# Django admin == the "super admin panel" (manage roles, view logins, settings) while no server exists.
admin.site.site_header = "پنل مدیریت سامانه رفاهیات هلال‌احمر"
admin.site.site_title = "رفاهیات | Super Admin"
admin.site.index_title = "مدیریت سامانه"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("identity.api.urls")),
    path("api/v1/", include("hr.api.urls")),
    # OpenAPI schema + docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

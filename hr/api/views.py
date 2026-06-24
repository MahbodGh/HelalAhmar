from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from hr.application import services as app
from hr.models import City, Dependent, OrgUnit, Personnel, PersonnelDecree, Province
from hr.api.serializers import (
    CitySerializer,
    DependentSerializer,
    OrgUnitSerializer,
    PersonnelDecreeSerializer,
    PersonnelDetailSerializer,
    PersonnelImportSerializer,
    PersonnelListSerializer,
    ProvinceSerializer,
)
from identity.api.pagination import StandardPagination
from identity.api.permissions import HasPermission


@extend_schema(tags=["hr-geo"])
class ProvinceListView(ListAPIView):
    """GET /api/v1/hr/provinces — list provinces (any authenticated user)."""

    queryset = Province.objects.all()
    serializer_class = ProvinceSerializer
    pagination_class = None


@extend_schema(tags=["hr-geo"])
class CityListView(ListAPIView):
    """GET /api/v1/hr/cities?province=<id> — list cities, optionally by province."""

    serializer_class = CitySerializer
    pagination_class = None

    def get_queryset(self):
        qs = City.objects.select_related("province").all()
        province = self.request.query_params.get("province")
        return qs.filter(province_id=province) if province else qs


@extend_schema(tags=["hr-org"])
class OrgUnitViewSet(viewsets.ModelViewSet):
    """Organizational units (tree). Read: hr.orgunit.view · Write: hr.orgunit.manage."""

    queryset = OrgUnit.objects.select_related("parent", "province", "city").all()
    serializer_class = OrgUnitSerializer
    pagination_class = None
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "code"]

    def get_permissions(self):
        code = "hr.orgunit.view" if self.request.method in ("GET", "HEAD", "OPTIONS") else "hr.orgunit.manage"
        return [HasPermission.of(code)()]

    @extend_schema(summary="درخت سازمانی", responses={200: OpenApiResponse(description="ساختار درختی")})
    @action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request):
        nodes = list(self.get_queryset())
        by_parent: dict = {}
        for n in nodes:
            by_parent.setdefault(n.parent_id, []).append(n)

        def build(parent_id):
            return [
                {
                    "id": n.id, "name": n.name, "code": n.code, "type": n.type,
                    "type_display": n.get_type_display(), "province": n.province_id,
                    "children": build(n.id),
                }
                for n in by_parent.get(parent_id, [])
            ]

        return Response(build(None))


@extend_schema(tags=["hr-personnel"])
class PersonnelViewSet(viewsets.ModelViewSet):
    """
    Personnel. Read: hr.personnel.view · Write: hr.personnel.manage.
    List is RLS-scoped to the caller's org subtree.
    """

    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["first_name", "last_name", "national_id", "personnel_no"]
    ordering_fields = ["last_name", "hire_date", "personnel_no"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        code = "hr.personnel.view" if self.request.method in ("GET", "HEAD", "OPTIONS") else "hr.personnel.manage"
        return [HasPermission.of(code)()]

    def get_serializer_class(self):
        return PersonnelListSerializer if self.action == "list" else PersonnelDetailSerializer

    def get_queryset(self):
        qs = app.scoped_personnel_qs(self.request.user)
        params = self.request.query_params
        for field in ("org_unit", "province", "employment_type", "employment_status"):
            if params.get(field):
                qs = qs.filter(**{f"{field}_id" if field in ("org_unit", "province") else field: params[field]})
        if params.get("is_retired") in ("true", "false"):
            qs = qs.filter(is_retired=(params["is_retired"] == "true"))
        if params.get("gender") in ("m", "f"):
            qs = qs.filter(gender=params["gender"])
        return qs

    @extend_schema(methods=["GET"], responses=DependentSerializer(many=True))
    @extend_schema(methods=["POST"], request=DependentSerializer, responses=DependentSerializer)
    @action(detail=True, methods=["get", "post"], url_path="dependents")
    def dependents(self, request, pk=None):
        person = self.get_object()
        if request.method == "POST":
            data = {**request.data, "personnel": person.id}
            ser = DependentSerializer(data=data)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        return Response(DependentSerializer(person.dependents.all(), many=True).data)

    @extend_schema(responses=PersonnelDecreeSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="decrees")
    def decrees(self, request, pk=None):
        person = self.get_object()
        return Response(PersonnelDecreeSerializer(person.decrees.all(), many=True).data)

    @extend_schema(
        request=PersonnelImportSerializer,
        responses={200: OpenApiResponse(description="{created, updated, total}")},
        summary="درون‌ریزی/همگام‌سازی پرسنل (hr.personnel.manage)",
    )
    @action(detail=False, methods=["post"], url_path="import")
    def import_personnel(self, request):
        ser = PersonnelImportSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(app.upsert_personnel(ser.validated_data["records"]), status=status.HTTP_200_OK)


@extend_schema(tags=["hr-personnel"])
class DependentViewSet(viewsets.ModelViewSet):
    """Manage dependents directly. Write: hr.personnel.manage."""

    queryset = Dependent.objects.select_related("personnel").all()
    serializer_class = DependentSerializer
    pagination_class = StandardPagination
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_permissions(self):
        code = "hr.personnel.view" if self.request.method in ("GET", "HEAD", "OPTIONS") else "hr.personnel.manage"
        return [HasPermission.of(code)()]

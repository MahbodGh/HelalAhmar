from rest_framework import serializers

from accommodation.models import (
    AccommodationComplex,
    AccommodationUnit,
    Amenity,
    SeasonalRate,
    UnitPlan,
)


class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ["id", "name", "scope", "icon", "is_active"]


class UnitPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitPlan
        fields = ["id", "name", "is_management", "description"]


class SeasonalRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeasonalRate
        fields = ["id", "unit", "label", "date_from", "date_to", "price"]


class ComplexListSerializer(serializers.ModelSerializer):
    province_name = serializers.CharField(source="province.name", read_only=True, default=None)
    units_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = AccommodationComplex
        fields = ["id", "name", "code", "province", "province_name", "city", "phone", "is_active", "units_count"]


class ComplexDetailSerializer(serializers.ModelSerializer):
    general_amenities = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Amenity.objects.all(), required=False
    )

    class Meta:
        model = AccommodationComplex
        fields = [
            "id", "name", "code", "address", "latitude", "longitude", "phone", "email",
            "org_unit", "province", "city",
            "manager", "executive_officer", "services_officer", "housekeeping_staff",
            "general_amenities", "is_active",
        ]


class UnitSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    complex_name = serializers.CharField(source="complex.name", read_only=True)

    class Meta:
        model = AccommodationUnit
        fields = [
            "id", "complex", "complex_name", "plan", "plan_name", "name_or_number",
            "standard_capacity", "max_capacity", "area_m2", "amenities",
            "status", "status_display", "is_management",
        ]


class UnitStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[c[0] for c in AccommodationUnit.STATUS_CHOICES])

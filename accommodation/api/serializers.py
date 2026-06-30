from rest_framework import serializers

from accommodation.models import (
    AccommodationComplex,
    AccommodationUnit,
    Amenity,
    LotteryEnrollment,
    LotteryRun,
    Reservation,
    ReservationPeriod,
    SeasonalRate,
    UnitPlan,
)


class LotteryEnrollmentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    personnel_name = serializers.CharField(source="personnel.full_name", read_only=True)
    persons = serializers.IntegerField(read_only=True)

    class Meta:
        model = LotteryEnrollment
        fields = [
            "id", "period", "personnel", "personnel_name", "first_degree_companions",
            "other_companions", "persons", "preferred_units", "score", "status",
            "status_display", "result_reservation", "created_at",
        ]
        read_only_fields = ["status", "result_reservation", "score"]


class EnrollLotterySerializer(serializers.Serializer):
    first_degree_companions = serializers.IntegerField(min_value=0, default=0)
    other_companions = serializers.IntegerField(min_value=0, default=0)
    preferred_units = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    personnel = serializers.IntegerField(required=False, allow_null=True)


class RunLotterySerializer(serializers.Serializer):
    seed = serializers.CharField(required=False, allow_blank=True, default="")


class LotteryRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = LotteryRun
        fields = ["id", "period", "seed", "total_enrollments", "winners_count", "created_at"]


class ReservationPeriodSerializer(serializers.ModelSerializer):
    method_display = serializers.CharField(source="get_method_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_enroll_open = serializers.BooleanField(read_only=True)

    class Meta:
        model = ReservationPeriod
        fields = [
            "id", "title", "method", "method_display", "status", "status_display",
            "enroll_start", "enroll_end", "stay_from", "stay_to",
            "min_nights", "max_nights", "max_total_companions", "allowed_capacity_increase",
            "block_if_used_within_days",
            "price_personnel", "price_first_degree_companion", "price_other_companion",
            "payment_methods", "payment_deadline_hours", "unit_selection_mode",
            "audience_rules", "province_quotas", "units", "org_unit", "province", "is_enroll_open",
        ]


class CreateReservationSerializer(serializers.Serializer):
    period = serializers.PrimaryKeyRelatedField(queryset=ReservationPeriod.objects.all())
    unit = serializers.PrimaryKeyRelatedField(queryset=AccommodationUnit.objects.all())
    check_in_date = serializers.DateField()
    check_out_date = serializers.DateField()
    first_degree_companions = serializers.IntegerField(min_value=0, default=0)
    other_companions = serializers.IntegerField(min_value=0, default=0)
    payment_method = serializers.CharField(required=False, allow_blank=True, default="")
    personnel = serializers.IntegerField(required=False, allow_null=True, help_text="فقط برای رزرو سازمانی")


class ReservationSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    persons = serializers.IntegerField(read_only=True)
    unit_name = serializers.CharField(source="unit.name_or_number", read_only=True)
    complex_name = serializers.CharField(source="unit.complex.name", read_only=True)
    personnel_name = serializers.CharField(source="personnel.full_name", read_only=True)

    class Meta:
        model = Reservation
        fields = [
            "id", "code", "period", "unit", "unit_name", "complex_name",
            "personnel", "personnel_name", "check_in_date", "check_out_date", "nights",
            "first_degree_companions", "other_companions", "persons",
            "total_cost", "payment_method", "status", "status_display",
            "payment_deadline", "is_refunded", "created_at",
        ]


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

from rest_framework import serializers

from hr.domain.value_objects import InvalidNationalIdError, NationalId
from hr.models import City, Dependent, OrgUnit, Personnel, PersonnelDecree, Province


def _validate_national_id(value: str) -> str:
    try:
        return NationalId.parse(value).value
    except InvalidNationalIdError as e:
        raise serializers.ValidationError(str(e))


class ProvinceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Province
        fields = ["id", "name", "code"]


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ["id", "name", "code", "province"]


class OrgUnitSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = OrgUnit
        fields = ["id", "name", "code", "type", "type_display", "parent", "province", "city", "is_active"]


class DependentSerializer(serializers.ModelSerializer):
    relation_display = serializers.CharField(source="get_relation_display", read_only=True)

    class Meta:
        model = Dependent
        fields = [
            "id", "personnel", "relation", "relation_display", "first_name", "last_name",
            "national_id", "birth_date", "gender", "is_student", "notes",
        ]

    def validate_national_id(self, value):
        normalized = _validate_national_id(value)
        qs = Dependent.objects.filter(national_id=normalized)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("فردی با این کد ملی قبلاً ثبت شده است.")
        return normalized


class PersonnelDecreeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonnelDecree
        fields = ["id", "personnel", "decree_no", "decree_date", "title", "attributes", "effective_from", "effective_to"]


class PersonnelListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    org_unit_name = serializers.CharField(source="org_unit.name", read_only=True, default=None)
    province_name = serializers.CharField(source="province.name", read_only=True, default=None)

    class Meta:
        model = Personnel
        fields = [
            "id", "national_id", "personnel_no", "full_name",
            "employment_type", "employment_status", "is_retired",
            "org_unit", "org_unit_name", "province", "province_name", "job_title",
        ]


class PersonnelDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    age = serializers.IntegerField(read_only=True)
    computed_service_years = serializers.IntegerField(read_only=True)
    dependents = DependentSerializer(many=True, read_only=True)
    decrees = PersonnelDecreeSerializer(many=True, read_only=True)

    class Meta:
        model = Personnel
        fields = [
            "id", "national_id", "personnel_no", "first_name", "last_name", "full_name",
            "gender", "birth_date", "age", "employment_type", "employment_status",
            "hire_date", "is_retired", "org_unit", "province", "job_title",
            "children_count", "service_years", "computed_service_years",
            "last_synced_at", "dependents", "decrees",
        ]
        read_only_fields = ["last_synced_at"]

    def validate_national_id(self, value):
        normalized = _validate_national_id(value)
        qs = Personnel.objects.filter(national_id=normalized)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("پرسنلی با این کد ملی قبلاً ثبت شده است.")
        return normalized


class PersonnelImportSerializer(serializers.Serializer):
    records = serializers.ListField(child=serializers.DictField(), allow_empty=False)

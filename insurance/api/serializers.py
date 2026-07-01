from rest_framework import serializers

from insurance.models import InsuranceClaim, InsurancePlan, InsuranceRequest


class InsurancePlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsurancePlan
        fields = [
            "id", "name", "code", "insurer_name", "description",
            "premium_per_person", "coverage_ceiling", "covered_services",
            "contract_start", "contract_end",
            "allow_dependents", "max_dependents", "is_active",
        ]


class _DependentBrief(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    relation = serializers.CharField(source="get_relation_display")


class InsuranceRequestSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    personnel_name = serializers.CharField(source="personnel.full_name", read_only=True)
    insured_count = serializers.IntegerField(read_only=True)
    dependents = _DependentBrief(source="insured_dependents", many=True, read_only=True)

    class Meta:
        model = InsuranceRequest
        fields = [
            "id", "code", "plan", "plan_name", "personnel", "personnel_name",
            "premium_total", "coverage_start", "coverage_end", "insured_count", "dependents",
            "status", "status_display", "submitted_at", "reviewed_at", "review_note", "created_at",
        ]


class CreateInsuranceRequestSerializer(serializers.Serializer):
    plan = serializers.PrimaryKeyRelatedField(queryset=InsurancePlan.objects.all())
    dependent_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    coverage_start = serializers.DateField(required=False, allow_null=True)
    coverage_end = serializers.DateField(required=False, allow_null=True)
    personnel = serializers.IntegerField(required=False, allow_null=True, help_text="فقط برای ثبت توسط کارشناس")


class ReviewSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default="")


class InsuranceClaimSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    personnel_name = serializers.CharField(source="personnel.full_name", read_only=True)
    patient_name = serializers.CharField(read_only=True)
    plan_name = serializers.CharField(source="request.plan.name", read_only=True)

    class Meta:
        model = InsuranceClaim
        fields = [
            "id", "code", "request", "plan_name", "personnel", "personnel_name",
            "patient_dependent", "patient_name", "service_type", "service_date",
            "claimed_amount", "approved_amount", "description", "documents",
            "status", "status_display", "submitted_at", "reviewed_at", "review_note",
            "paid_at", "created_at",
        ]


class CreateClaimSerializer(serializers.Serializer):
    request = serializers.PrimaryKeyRelatedField(queryset=InsuranceRequest.objects.all())
    service_type = serializers.CharField()
    claimed_amount = serializers.IntegerField(min_value=1)
    service_date = serializers.DateField(required=False, allow_null=True)
    patient_dependent_id = serializers.IntegerField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    documents = serializers.ListField(required=False, default=list)


class ApproveClaimSerializer(serializers.Serializer):
    approved_amount = serializers.IntegerField(min_value=0)
    note = serializers.CharField(required=False, allow_blank=True, default="")

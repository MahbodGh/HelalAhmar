from rest_framework import serializers

from loan.models import LoanRequest, LoanType


class LoanTypeSerializer(serializers.ModelSerializer):
    allocation_display = serializers.CharField(source="get_allocation_method_display", read_only=True)

    class Meta:
        model = LoanType
        fields = [
            "id", "name", "code", "description", "max_amount", "max_installments",
            "profit_rate", "fund_budget", "allocation_method", "allocation_display",
            "block_if_active_loan", "audience_rules", "is_active",
        ]


class LoanRequestSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    loan_type_name = serializers.CharField(source="loan_type.name", read_only=True)
    personnel_name = serializers.CharField(source="personnel.full_name", read_only=True)

    class Meta:
        model = LoanRequest
        fields = [
            "id", "code", "loan_type", "loan_type_name", "personnel", "personnel_name",
            "requested_amount", "installments_count", "reason",
            "approved_amount", "monthly_installment",
            "status", "status_display", "submitted_at", "reviewed_at", "review_note",
            "disbursed_at", "created_at",
        ]


class CreateLoanRequestSerializer(serializers.Serializer):
    loan_type = serializers.PrimaryKeyRelatedField(queryset=LoanType.objects.all())
    requested_amount = serializers.IntegerField(min_value=1)
    installments_count = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    personnel = serializers.IntegerField(required=False, allow_null=True, help_text="فقط برای ثبت توسط کارشناس")


class ApproveLoanSerializer(serializers.Serializer):
    approved_amount = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class ReviewSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default="")

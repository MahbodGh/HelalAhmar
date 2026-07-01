from rest_framework import serializers

from referral.models import ContractedProvider, ReferralLetter


class ContractedProviderSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = ContractedProvider
        fields = [
            "id", "name", "code", "category", "category_display",
            "province", "city", "address", "phone",
            "discount_percent", "terms", "contract_start", "contract_end", "is_active",
        ]


class ReferralLetterSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    provider_name = serializers.CharField(source="provider.name", read_only=True)
    personnel_name = serializers.CharField(source="personnel.full_name", read_only=True)
    beneficiary_name = serializers.CharField(read_only=True)

    class Meta:
        model = ReferralLetter
        fields = [
            "id", "code", "provider", "provider_name", "personnel", "personnel_name",
            "beneficiary_dependent", "beneficiary_name", "service_description", "note",
            "status", "status_display", "issued_at", "valid_until", "review_note", "created_at",
        ]


class CreateReferralLetterSerializer(serializers.Serializer):
    provider = serializers.PrimaryKeyRelatedField(queryset=ContractedProvider.objects.all())
    service_description = serializers.CharField()
    beneficiary_dependent_id = serializers.IntegerField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, default="")
    personnel = serializers.IntegerField(required=False, allow_null=True, help_text="فقط برای ثبت توسط کارشناس")


class IssueLetterSerializer(serializers.Serializer):
    valid_until = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class ReviewSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default="")

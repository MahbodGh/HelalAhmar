from rest_framework import serializers

from finance.models import DeductionBatch, DeductionItem


class DeductionBatchSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = DeductionBatch
        fields = [
            "id", "period", "title", "org_unit", "status", "status_display",
            "total_amount", "item_count", "generated_at", "finalized_at", "exported_at", "created_at",
        ]
        read_only_fields = ["status", "total_amount", "item_count", "generated_at", "finalized_at", "exported_at"]


class DeductionItemSerializer(serializers.ModelSerializer):
    source_display = serializers.CharField(source="get_source_type_display", read_only=True)
    personnel_name = serializers.CharField(source="personnel.full_name", read_only=True)
    personnel_no = serializers.CharField(source="personnel.personnel_no", read_only=True)

    class Meta:
        model = DeductionItem
        fields = [
            "id", "batch", "personnel", "personnel_name", "personnel_no",
            "source_type", "source_display", "source_ref", "amount", "description",
        ]


class AddItemSerializer(serializers.Serializer):
    personnel = serializers.IntegerField()
    amount = serializers.IntegerField(min_value=1)
    description = serializers.CharField(required=False, allow_blank=True, default="")

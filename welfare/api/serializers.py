from rest_framework import serializers

from welfare.models import WelfareNote


class WelfareNoteSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    author_name = serializers.CharField(source="author.full_name", read_only=True)

    class Meta:
        model = WelfareNote
        fields = ["id", "personnel", "category", "category_display", "text", "author_name", "created_at"]
        read_only_fields = ["author_name", "created_at"]

from rest_framework import serializers

from identity.models import Permission, Role


class OtpRequestSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=13)


class OtpVerifySerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=13)
    code = serializers.CharField(max_length=8)


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "code", "name", "module"]


class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SlugRelatedField(
        slug_field="code", many=True, queryset=Permission.objects.all(), required=False
    )

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "is_system", "permissions"]
        read_only_fields = ["is_system"]

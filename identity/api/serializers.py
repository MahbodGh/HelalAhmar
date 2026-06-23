from rest_framework import serializers

from identity.models import Dashboard, LoginAudit, Permission, Role, User, UserRole


class UserRoleSerializer(serializers.ModelSerializer):
    role_code = serializers.CharField(source="role.code", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = UserRole
        fields = ["id", "role_code", "role_name", "scope_org_unit_id", "is_active"]


class UserAdminSerializer(serializers.ModelSerializer):
    is_super_admin = serializers.BooleanField(read_only=True)
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "mobile", "full_name", "is_active",
            "is_super_admin", "date_joined", "last_login_at", "roles",
        ]
        read_only_fields = ["id", "is_super_admin", "date_joined", "last_login_at", "roles"]

    def get_roles(self, obj):
        qs = obj.user_roles.filter(is_active=True).select_related("role")
        return UserRoleSerializer(qs, many=True).data

    def validate_mobile(self, value):
        from identity.domain.value_objects import InvalidMobileError, Mobile
        try:
            normalized = Mobile.parse(value).value
        except InvalidMobileError:
            raise serializers.ValidationError("شماره موبایل نامعتبر است.")
        qs = User.objects.filter(mobile=normalized)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("کاربری با این موبایل قبلاً ثبت شده است.")
        return normalized

    def create(self, validated_data):
        from identity.application import services as app
        return app.create_user_account(**validated_data)


class AssignRoleSerializer(serializers.Serializer):
    role_code = serializers.CharField()
    scope_org_unit_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_role_code(self, value):
        if not Role.objects.filter(code=value).exists():
            raise serializers.ValidationError("نقشی با این کد وجود ندارد.")
        return value


class LoginAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginAudit
        fields = ["id", "mobile", "success", "reason", "ip_address", "user_agent", "created_at", "user"]


class DashboardSerializer(serializers.ModelSerializer):
    required_permission = serializers.SlugRelatedField(slug_field="code", read_only=True)

    class Meta:
        model = Dashboard
        fields = ["code", "title", "description", "icon", "route", "group", "required_permission", "order"]


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

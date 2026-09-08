from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """User representation that accepts, but never exposes, a password."""

    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)

    class Meta:
        model = User
        fields = [
            "id", "email", "password", "phone_number", "first_name", "last_name",
            "is_active", "is_staff", "is_verified", "last_login_at", "last_login_ip",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "last_login_at", "last_login_ip", "created_at", "updated_at"]

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        if not password:
            raise serializers.ValidationError({"password": "This field is required."})
        return User.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attribute, value in validated_data.items():
            setattr(instance, attribute, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
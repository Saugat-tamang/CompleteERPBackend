from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAdminUser

from .models import (
    Invitation, LoginHistory, MFADevice, Permission, RefreshToken, Role,
    RolePermission, SocialAccount, TokenBlacklist, User, UserCompany,
    UserCompanyRole, UserProfile,
)
from .serializers import UserSerializer


def model_serializer(model, *, write_only_fields=()):
    """Create a CRUD serializer while keeping credential values private."""
    meta = type(
        "Meta", (),
        {
            "model": model,
            "fields": "__all__",
            "extra_kwargs": {field: {"write_only": True} for field in write_only_fields},
        },
    )
    return type(f"{model.__name__}Serializer", (serializers.ModelSerializer,), {"Meta": meta})


class AdminModelViewSet(viewsets.ModelViewSet):
    """Platform administration endpoint; normal ERP users must not use it."""

    permission_classes = [IsAdminUser]


class UserViewSet(AdminModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserProfileViewSet(AdminModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = model_serializer(UserProfile)


class RefreshTokenViewSet(AdminModelViewSet):
    queryset = RefreshToken.objects.all()
    serializer_class = model_serializer(RefreshToken, write_only_fields=("token",))


class LoginHistoryViewSet(AdminModelViewSet):
    queryset = LoginHistory.objects.all()
    serializer_class = model_serializer(LoginHistory)


class MFADeviceViewSet(AdminModelViewSet):
    queryset = MFADevice.objects.all()
    serializer_class = model_serializer(MFADevice, write_only_fields=("secret",))


class SocialAccountViewSet(AdminModelViewSet):
    queryset = SocialAccount.objects.all()
    serializer_class = model_serializer(SocialAccount, write_only_fields=("access_token", "refresh_token"))


class UserCompanyViewSet(AdminModelViewSet):
    queryset = UserCompany.all_objects.all()
    serializer_class = model_serializer(UserCompany)


class RoleViewSet(AdminModelViewSet):
    queryset = Role.all_objects.all()
    serializer_class = model_serializer(Role)


class PermissionViewSet(AdminModelViewSet):
    queryset = Permission.objects.all()
    serializer_class = model_serializer(Permission)


class RolePermissionViewSet(AdminModelViewSet):
    queryset = RolePermission.objects.all()
    serializer_class = model_serializer(RolePermission)


class UserCompanyRoleViewSet(AdminModelViewSet):
    queryset = UserCompanyRole.all_objects.all()
    serializer_class = model_serializer(UserCompanyRole)


class InvitationViewSet(AdminModelViewSet):
    queryset = Invitation.objects.all()
    serializer_class = model_serializer(Invitation)


class TokenBlacklistViewSet(AdminModelViewSet):
    queryset = TokenBlacklist.objects.all()
    serializer_class = model_serializer(TokenBlacklist)

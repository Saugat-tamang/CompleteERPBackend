from rest_framework.routers import DefaultRouter

from .views import (
    InvitationViewSet, LoginHistoryViewSet, MFADeviceViewSet, PermissionViewSet,
    RefreshTokenViewSet, RolePermissionViewSet, RoleViewSet, SocialAccountViewSet,
    TokenBlacklistViewSet, UserCompanyRoleViewSet, UserCompanyViewSet,
    UserProfileViewSet, UserViewSet,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("profiles", UserProfileViewSet, basename="profile")
router.register("refresh-tokens", RefreshTokenViewSet, basename="refresh-token")
router.register("login-history", LoginHistoryViewSet, basename="login-history")
router.register("mfa-devices", MFADeviceViewSet, basename="mfa-device")
router.register("social-accounts", SocialAccountViewSet, basename="social-account")
router.register("user-companies", UserCompanyViewSet, basename="user-company")
router.register("roles", RoleViewSet, basename="role")
router.register("permissions", PermissionViewSet, basename="permission")
router.register("role-permissions", RolePermissionViewSet, basename="role-permission")
router.register("user-company-roles", UserCompanyRoleViewSet, basename="user-company-role")
router.register("invitations", InvitationViewSet, basename="invitation")
router.register("token-blacklist", TokenBlacklistViewSet, basename="token-blacklist")

urlpatterns = router.urls

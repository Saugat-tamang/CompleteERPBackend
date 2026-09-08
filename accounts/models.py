"""
accounts/models.py

Identity & access — shared across all tenants (lives in the shared DB,
never in a per-tenant database). A single User can belong to many
Companies via UserCompany, exactly like Zoho's account-switcher.
"""
import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from system_core.models import BaseModel, TrackedModel, FullBaseModel


# ===========================================================================
# User
# ===========================================================================

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_("Email is required"))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    """
    Global identity — intentionally has NO company field. Company
    membership/role is expressed through UserCompany + UserCompanyRole,
    since one person can belong to multiple orgs.
    """
    email = models.EmailField(unique=True, db_index=True)
    phone_number = models.CharField(max_length=20, blank=True)

    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)   # Django admin access
    is_verified = models.BooleanField(default=False)  # email verified

    last_login_at = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "accounts_user"

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email


class UserProfile(BaseModel):
    """1:1 extension of User for non-auth-critical fields."""
    user = models.OneToOneField(User, related_name="profile", on_delete=models.CASCADE)
    avatar_url = models.URLField(blank=True)
    timezone = models.ForeignKey("system_core.TimeZone", null=True, blank=True, on_delete=models.SET_NULL)
    language = models.ForeignKey("system_core.Language", null=True, blank=True, on_delete=models.SET_NULL)
    date_format = models.CharField(max_length=20, default="YYYY-MM-DD")

    class Meta:
        db_table = "accounts_user_profile"

    def __str__(self):
        return f"Profile({self.user.email})"


# ===========================================================================
# JWT / session tracking
# ===========================================================================

class RefreshToken(BaseModel):
    """
    Persisted refresh tokens so they can be revoked/blacklisted server-side
    (access tokens stay short-lived and stateless; this table is only for
    the longer-lived refresh token half of the JWT pair).
    """
    user = models.ForeignKey(User, related_name="refresh_tokens", on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True, db_index=True)
    company = models.ForeignKey("tenants.Company", null=True, blank=True,related_name="+", on_delete=models.SET_NULL,help_text="Which company context this session was issued for, if any.",)
    device_info = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    expires_at = models.DateTimeField()
    is_revoked = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_refresh_token"
        indexes = [models.Index(fields=["user", "is_revoked"])]

    def __str__(self):
        return f"RefreshToken({self.user.email})"

    def revoke(self):
        self.is_revoked = True
        self.revoked_at = timezone.now()
        self.save(update_fields=["is_revoked", "revoked_at"])

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at


class TokenBlacklist(BaseModel):
    """Blacklisted access-token JTIs, checked on each request until natural expiry."""
    jti = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(User, related_name="blacklisted_tokens", on_delete=models.CASCADE)
    blacklisted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "accounts_token_blacklist"


class LoginHistory(BaseModel):
    """Login attempt audit trail — separate from ActivityLog, purpose-built for security screens."""
    user = models.ForeignKey(User, null=True, blank=True, related_name="login_history", on_delete=models.SET_NULL)
    email_attempted = models.EmailField()
    was_successful = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    company = models.ForeignKey("tenants.Company", null=True, blank=True, related_name="+", on_delete=models.SET_NULL)

    class Meta:
        db_table = "accounts_login_history"
        ordering = ["-created_at"]
        verbose_name_plural = "login history"


class MFAMethod(models.TextChoices):
    TOTP = "totp", "Authenticator App"
    SMS = "sms", "SMS"
    EMAIL = "email", "Email"


class MFADevice(BaseModel):
    user = models.ForeignKey(User, related_name="mfa_devices", on_delete=models.CASCADE)
    method = models.CharField(max_length=10, choices=MFAMethod.choices)
    secret = models.CharField(max_length=255)  # store encrypted at the app layer
    is_primary = models.BooleanField(default=False)
    is_confirmed = models.BooleanField(default=False)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_mfa_device"
        unique_together = [("user", "method")]


class SocialProvider(models.TextChoices):
    GOOGLE = "google", "Google"
    MICROSOFT = "microsoft", "Microsoft"
    GITHUB = "github", "GitHub"


class SocialAccount(BaseModel):
    user = models.ForeignKey(User, related_name="social_accounts", on_delete=models.CASCADE)
    provider = models.CharField(max_length=20, choices=SocialProvider.choices)
    provider_uid = models.CharField(max_length=255)
    access_token = models.TextField(blank=True)  # store encrypted at the app layer
    refresh_token = models.TextField(blank=True)

    class Meta:
        db_table = "accounts_social_account"
        unique_together = [("provider", "provider_uid")]


# ===========================================================================
# Companies membership, roles & permissions
# ===========================================================================

class UserCompany(FullBaseModel):
    """
    Join table: which companies a user belongs to. Zoho-style: a user logs
    in once and switches between companies they're a member of.
    """
    user = models.ForeignKey(User, related_name="user_companies", on_delete=models.CASCADE)
    company = models.ForeignKey("tenants.Company", related_name="user_companies", on_delete=models.CASCADE)
    is_default = models.BooleanField(default=False, help_text="Company selected on login by default.")
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "accounts_user_company"
        unique_together = [("user", "company")]

    def __str__(self):
        return f"{self.user.email} @ {self.company_id}"


class Role(FullBaseModel):
    """
    Roles are defined per-company (not global) so each org can create its
    own custom roles (e.g. 'Regional Manager') in addition to system
    defaults like Admin/Staff.
    """
    company = models.ForeignKey(
        "tenants.Company", null=True, blank=True,
        related_name="roles", on_delete=models.CASCADE,
        help_text="Null for system-wide default roles (Admin, Staff, etc.)",
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_system_role = models.BooleanField(default=False, help_text="System roles can't be edited/deleted by tenants.")

    class Meta:
        db_table = "accounts_role"
        unique_together = [("company", "name")]

    def __str__(self):
        return self.name


class Permission(BaseModel):
    """
    Granular permission catalog, e.g. 'invoice.create', 'user.invite'.
    Global/system-defined — not per-tenant, since the set of things the
    software CAN do doesn't change per company.
    """
    code = models.SlugField(max_length=150, unique=True)  # "invoice.create"
    module = models.CharField(max_length=100)             # "invoice"
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "accounts_permission"
        ordering = ["module", "code"]

    def __str__(self):
        return self.code


class RolePermission(BaseModel):
    role = models.ForeignKey(Role, related_name="role_permissions", on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, related_name="role_permissions", on_delete=models.CASCADE)

    class Meta:
        db_table = "accounts_role_permission"
        unique_together = [("role", "permission")]

    def __str__(self):
        return f"{self.role.name} -> {self.permission.code}"


class UserCompanyRole(FullBaseModel):
    """
    A user's role is scoped PER company: Admin in one org, Staff in
    another. This is the table actual permission checks resolve through.
    """
    user_company = models.ForeignKey(UserCompany, related_name="roles", on_delete=models.CASCADE)
    role = models.ForeignKey(Role, related_name="user_company_roles", on_delete=models.CASCADE)

    class Meta:
        db_table = "accounts_user_company_role"
        unique_together = [("user_company", "role")]

    def __str__(self):
        return f"{self.user_company} -> {self.role.name}"


class InvitationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    EXPIRED = "expired", "Expired"
    REVOKED = "revoked", "Revoked"


class Invitation(TrackedModel):
    """Pending invite for someone to join a company, optionally pre-assigned a role."""
    company = models.ForeignKey("tenants.Company", related_name="invitations", on_delete=models.CASCADE)
    email = models.EmailField()
    role = models.ForeignKey(Role, null=True, blank=True, related_name="+", on_delete=models.SET_NULL)
    token = models.CharField(max_length=128, unique=True, default=uuid.uuid4)
    status = models.CharField(max_length=10, choices=InvitationStatus.choices, default=InvitationStatus.PENDING)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_invitation"
        unique_together = [("company", "email")]

    def __str__(self):
        return f"Invite({self.email} -> {self.company_id})"
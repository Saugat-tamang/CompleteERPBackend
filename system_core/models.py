"""
system_core/models.py

Shared infrastructure models. Nothing in this file should import from
`accounts` or `tenants` directly (use settings.AUTH_USER_MODEL and string
references like "tenants.Company" instead) to avoid circular imports —
accounts and tenants both depend on system_core, not the other way around.
"""

import contextvars
import uuid
from contextlib import contextmanager

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ===========================================================================
# Tenant context (thread-local / contextvar) — used by TenantManager below
# and by the DB router for per-tenant-database routing.
# ===========================================================================

_current_tenant = contextvars.ContextVar("current_tenant", default=None)


def get_current_tenant():
    return _current_tenant.get()


def set_current_tenant(company):
    return _current_tenant.set(company)


def clear_current_tenant(token=None):
    if token is not None:
        _current_tenant.reset(token)
    else:
        _current_tenant.set(None)


@contextmanager
def tenant_context(company):
    """with tenant_context(some_company): ... scoped code ..."""
    token = set_current_tenant(company)
    try:
        yield company
    finally:
        clear_current_tenant(token)


# ===========================================================================
# Base abstract models
# ===========================================================================

class BaseModel(models.Model):
    """UUID primary key + created_at/updated_at. Root of every model in the system."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.__class__.__name__}({self.id})"


class AuditModel(models.Model):
    """created_by / updated_by actor tracking, on top of BaseModel's timestamps."""
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        related_name="+", on_delete=models.SET_NULL, editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        related_name="+", on_delete=models.SET_NULL, editable=False,
    )

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)

    def delete(self):
        return super().update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteModel(models.Model):
    """Soft-delete semantics: default manager hides deleted rows; all_objects sees everything."""
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        related_name="+", on_delete=models.SET_NULL, editable=False,
    )

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, deleted_by=None, hard=False):
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if deleted_by is not None:
            self.deleted_by = deleted_by
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])


class TrackedModel(BaseModel, AuditModel):
    """UUID + timestamps + created_by/updated_by. No soft delete."""

    class Meta:
        abstract = True


class FullBaseModel(BaseModel, AuditModel, SoftDeleteModel):
    """The default for real business models: UUID + timestamps + actors + soft delete."""

    class Meta:
        abstract = True


class TenantManager(models.Manager):
    """
    Automatically filters records by the current tenant.

    Tenant context must be established by middleware/service code before
    accessing tenant-scoped models. Use ``unscoped()`` only for controlled
    system/platform operations.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = get_current_tenant()
        if tenant is None:
            raise RuntimeError(
                "Tenant context is required for tenant-scoped queries."
            )
        return qs.filter(company_id=tenant.id)

    def unscoped(self):
        """Explicitly bypass tenant filtering for platform operations."""
        return super().get_queryset()


class TenantScopedModel(FullBaseModel):
    """
    For models kept in the SHARED database that still need tenant scoping.
    Does NOT apply to models routed into a per-tenant physical database via
    tenants.TenantDatabase — those are already isolated by connection.
    """
    company = models.ForeignKey(
        "tenants.Company", related_name="%(class)ss",
        on_delete=models.CASCADE, db_index=True,
    )

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True


# ===========================================================================
# Generic activity log
# ===========================================================================

class ActivityAction(models.TextChoices):
    CREATE = "create", _("Create")
    UPDATE = "update", _("Update")
    DELETE = "delete", _("Delete")
    RESTORE = "restore", _("Restore")
    LOGIN = "login", _("Login")
    LOGOUT = "logout", _("Logout")
    LOGIN_FAILED = "login_failed", _("Login Failed")
    PERMISSION_CHANGE = "permission_change", _("Permission Change")
    EXPORT = "export", _("Export")
    IMPORT = "import", _("Import")
    APPROVE = "approve", _("Approve")
    REJECT = "reject", _("Reject")
    INVITE = "invite", _("Invite")
    OTHER = "other", _("Other")


class ActivityLog(BaseModel):
    """Platform-wide 'what happened' audit trail. Lives in the shared DB."""
    company_id = models.UUIDField(null=True, blank=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        related_name="activity_logs", on_delete=models.SET_NULL,
    )
    action = models.CharField(max_length=32, choices=ActivityAction.choices)

    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    object_id = models.UUIDField(null=True, blank=True)
    target = GenericForeignKey("content_type", "object_id")
    target_repr = models.CharField(max_length=255, blank=True)

    changes = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "system_core_activity_log"
        indexes = [
            models.Index(fields=["company_id", "created_at"]),
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.actor} {self.action} {self.target_repr}"


# ===========================================================================
# Reference / lookup data
# ===========================================================================

class Country(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    iso2 = models.CharField(max_length=2, unique=True)
    iso3 = models.CharField(max_length=3, unique=True)
    phone_code = models.CharField(max_length=10, blank=True)
    flag_emoji = models.CharField(max_length=8, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "system_core_country"
        ordering = ["name"]
        verbose_name_plural = "countries"

    def __str__(self):
        return self.name


class Currency(BaseModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=3, unique=True)
    symbol = models.CharField(max_length=8)
    decimal_places = models.PositiveSmallIntegerField(default=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "system_core_currency"
        ordering = ["code"]
        verbose_name_plural = "currencies"

    def __str__(self):
        return self.code


class Language(BaseModel):
    name = models.CharField(max_length=100)
    native_name = models.CharField(max_length=100, blank=True)
    code = models.CharField(max_length=10, unique=True)
    is_rtl = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "system_core_language"
        ordering = ["name"]

    def __str__(self):
        return self.name


class TimeZone(BaseModel):
    name = models.CharField(max_length=64, unique=True)
    utc_offset_minutes = models.IntegerField()
    display_label = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "system_core_timezone"
        ordering = ["utc_offset_minutes"]

    def __str__(self):
        return self.display_label or self.name


# ===========================================================================
# Platform-level config
# ===========================================================================

class FeatureFlag(TrackedModel):
    """Global kill-switches / staged rollouts (e.g. 'new_invoice_ui'). Not per-tenant."""
    key = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=False)
    rollout_percentage = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "system_core_feature_flag"
        ordering = ["key"]

    def __str__(self):
        return self.key


class SystemConfigCategory(models.TextChoices):
    GENERAL = "general", "General"
    SECURITY = "security", "Security"
    EMAIL = "email", "Email"
    BILLING = "billing", "Billing"
    INTEGRATION = "integration", "Integration"


class SystemConfig(TrackedModel):
    """Key/value store for global settings that shouldn't live in code/env."""
    key = models.SlugField(max_length=150, unique=True)
    value = models.JSONField()
    category = models.CharField(max_length=32, choices=SystemConfigCategory.choices, default=SystemConfigCategory.GENERAL)
    description = models.TextField(blank=True)
    is_sensitive = models.BooleanField(default=False)

    class Meta:
        db_table = "system_core_config"
        ordering = ["category", "key"]

    def __str__(self):
        return self.key

"""
Organization & billing — Company is the tenant. TenantDatabase drives DB
routing for tenants that get a fully isolated per-tenant database; tenants
that don't need one simply have no TenantDatabase row and stay on the
shared/default DB with tenant-scoped tables (system_core.TenantScopedModel).
"""

import uuid
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from system_core.models import BaseModel, TrackedModel, FullBaseModel


# ===========================================================================
# Company (the tenant)
# ===========================================================================

class CompanySize(models.TextChoices):
    SOLO = "solo", "Just me"
    SMALL = "1-10", "1-10 employees"
    MEDIUM = "11-50", "11-50 employees"
    LARGE = "51-200", "51-200 employees"
    ENTERPRISE = "200+", "200+ employees"


class Industry(BaseModel):
    """System-defined industry list, shown at signup (Zoho-style) to drive default templates/settings."""
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "tenants_industry"
        ordering = ["name"]
        verbose_name_plural = "industries"

    def __str__(self):
        return self.name


class CompanyStatus(models.TextChoices):
    PENDING = "pending", "Pending Setup"
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    CANCELLED = "cancelled", "Cancelled"


class Company(FullBaseModel):
    """The tenant itself. One row per organization/account."""
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)  # used for subdomain: {slug}.yourapp.com

    industry = models.ForeignKey(Industry, null=True, blank=True, related_name="companies", on_delete=models.SET_NULL)
    company_size = models.CharField(max_length=10, choices=CompanySize.choices, blank=True)

    country = models.ForeignKey("system_core.Country", null=True, blank=True, on_delete=models.SET_NULL)
    default_currency = models.ForeignKey("system_core.Currency", null=True, blank=True, on_delete=models.SET_NULL)
    default_timezone = models.ForeignKey("system_core.TimeZone", null=True, blank=True, on_delete=models.SET_NULL)
    default_language = models.ForeignKey("system_core.Language", null=True, blank=True, on_delete=models.SET_NULL)

    status = models.CharField(max_length=12, choices=CompanyStatus.choices, default=CompanyStatus.PENDING)
    logo_url = models.URLField(blank=True)

    class Meta:
        db_table = "tenants_company"

    def __str__(self):
        return self.name


class CompanyDomain(BaseModel):
    """
    Domain -> Company resolution. Supports both the platform subdomain
    ({slug}.yourapp.com) and customer-owned custom domains, used by
    tenant-resolution middleware on every incoming request.
    """
    company = models.ForeignKey(Company, related_name="domains", on_delete=models.CASCADE)
    domain = models.CharField(max_length=255, unique=True, db_index=True)
    is_primary = models.BooleanField(default=False)
    is_custom = models.BooleanField(default=False)  # False = platform subdomain, True = customer's own domain
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tenants_company_domain"

    def __str__(self):
        return self.domain


# ===========================================================================
# Tenant database routing / provisioning
# ===========================================================================

class TenantDatabase(BaseModel):
    """
    Physical/schema database this company's isolated data lives in. Absence
    of a row here (for a shared-DB tenant) means the DB router falls back
    to the default connection and tenant-scoped shared tables are used
    instead.
    """
    company = models.OneToOneField(Company, related_name="tenant_database", on_delete=models.CASCADE)
    alias = models.CharField(max_length=100, unique=True, help_text="Key registered in Django DATABASES setting.")
    engine = models.CharField(max_length=100, default="django.db.backends.postgresql")
    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField(default=5432)
    database_name = models.CharField(max_length=100)
    username = models.CharField(max_length=100)
    password_secret_ref = models.CharField(
        max_length=255,
        help_text="Reference/key into a secrets manager — never store the raw password here.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "tenants_tenant_database"

    def __str__(self):
        return f"{self.company.name} -> {self.alias}"


class ProvisioningStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    CREATING_DATABASE = "creating_database", "Creating Database"
    RUNNING_MIGRATIONS = "running_migrations", "Running Migrations"
    SEEDING_DATA = "seeding_data", "Seeding Data"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class ProvisioningLog(BaseModel):
    """Tracks async steps of spinning up a new tenant (DB creation, migrations, seed data)."""
    company = models.ForeignKey(Company, related_name="provisioning_logs", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=ProvisioningStatus.choices, default=ProvisioningStatus.QUEUED)
    step_detail = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tenants_provisioning_log"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.company.name} [{self.status}]"


# Backwards-compatible name for callers created before the model was renamed.
TenantProvisioningLog = ProvisioningLog


# ===========================================================================
# Plans, subscriptions, features, billing
# ===========================================================================

class BillingCycle(models.TextChoices):
    MONTHLY = "monthly", "Monthly"
    YEARLY = "yearly", "Yearly"


class Plan(TrackedModel):
    """A purchasable plan tier, e.g. Free, Standard, Professional, Enterprise."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_users = models.PositiveIntegerField(null=True, blank=True, help_text="Null = unlimited.")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "tenants_plan"
        ordering = ["sort_order"]

    def __str__(self):
        return self.name


class PlanFeature(BaseModel):
    """Which feature keys a given Plan unlocks by default (baseline entitlements)."""
    plan = models.ForeignKey(Plan, related_name="features", on_delete=models.CASCADE)
    feature_key = models.SlugField(max_length=100)
    limit_value = models.IntegerField(null=True, blank=True, help_text="Null = unlimited/boolean feature.")

    class Meta:
        db_table = "tenants_plan_feature"
        unique_together = [("plan", "feature_key")]

    def __str__(self):
        return f"{self.plan.name}: {self.feature_key}"


class SubscriptionStatus(models.TextChoices):
    TRIALING = "trialing", "Trialing"
    ACTIVE = "active", "Active"
    PAST_DUE = "past_due", "Past Due"
    CANCELLED = "cancelled", "Cancelled"
    EXPIRED = "expired", "Expired"


class Subscription(TrackedModel):
    """Which plan a company is currently on, and its billing state."""
    company = models.OneToOneField(Company, related_name="subscription", on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, related_name="subscriptions", on_delete=models.PROTECT)
    billing_cycle = models.CharField(max_length=10, choices=BillingCycle.choices, default=BillingCycle.MONTHLY)
    status = models.CharField(max_length=12, choices=SubscriptionStatus.choices, default=SubscriptionStatus.TRIALING)

    trial_ends_at = models.DateTimeField(null=True, blank=True)
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    external_customer_id = models.CharField(max_length=255, blank=True, help_text="e.g. Stripe customer ID.")
    external_subscription_id = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "tenants_subscription"

    def __str__(self):
        return f"{self.company.name}: {self.plan.name} ({self.status})"


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    OPEN = "open", "Open"
    PAID = "paid", "Paid"
    VOID = "void", "Void"
    UNCOLLECTIBLE = "uncollectible", "Uncollectible"


class Invoice(TrackedModel):
    """Platform billing invoice for a company's subscription (not a tenant's own customer invoices)."""
    company = models.ForeignKey(Company, related_name="invoices", on_delete=models.CASCADE)
    subscription = models.ForeignKey(Subscription, related_name="invoices", on_delete=models.SET_NULL, null=True, blank=True)
    invoice_number = models.CharField(max_length=50, unique=True)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.ForeignKey("system_core.Currency", on_delete=models.PROTECT)
    status = models.CharField(max_length=15, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT)
    due_date = models.DateField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    external_invoice_id = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "tenants_invoice"
        ordering = ["-created_at"]

    def __str__(self):
        return self.invoice_number


class CompanyFeature(TrackedModel):
    """
    Feature overrides for a SPECIFIC company beyond what its Plan grants —
    e.g. a manually-enabled enterprise add-on, or a temporary trial unlock.
    """
    company = models.ForeignKey(Company, related_name="feature_overrides", on_delete=models.CASCADE)
    feature_key = models.SlugField(max_length=100)
    is_enabled = models.BooleanField(default=True)
    limit_value = models.IntegerField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Null = permanent override.")
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "tenants_company_feature"
        unique_together = [("company", "feature_key")]

    def __str__(self):
        return f"{self.company.name}: {self.feature_key}"


class CompanySettings(BaseModel):
    """1:1 general settings/preferences bucket for a company (non-billing, non-plan)."""
    company = models.OneToOneField(Company, related_name="settings", on_delete=models.CASCADE)
    fiscal_year_start_month = models.PositiveSmallIntegerField(default=1)
    date_format = models.CharField(max_length=20, default="YYYY-MM-DD")
    time_format_24h = models.BooleanField(default=True)
    allow_self_signup = models.BooleanField(default=False, help_text="Allow users with a matching email domain to auto-join.")
    email_domain_whitelist = models.JSONField(default=list, blank=True)
    custom_settings = models.JSONField(default=dict, blank=True, help_text="Free-form settings bucket for module-specific config.")

    class Meta:
        db_table = "tenants_company_settings"

    def __str__(self):
        return f"Settings({self.company.name})"

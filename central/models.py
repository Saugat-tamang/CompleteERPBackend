import uuid
import secrets
from django.db import models


# ------------------------------------------------------------
# CHOICES
# ------------------------------------------------------------

def generate_org_id():
    return secrets.randbelow(9_000_000_000) + 1_000_000_000

class CompanySize(models.TextChoices):
    SELF_EMPLOYED = "SELF_EMPLOYED", "1 (Self-employed)"
    SMALL = "SMALL", "2-10"
    MEDIUM = "MEDIUM", "11-50"
    LARGE = "LARGE", "51-200"
    ENTERPRISE = "ENTERPRISE", "200+"


class CompanyStatus(models.TextChoices):
    TRIAL = "TRIAL", "Trial"
    ACTIVE = "ACTIVE", "Active"
    PAST_DUE = "PAST_DUE", "Past Due"
    SUSPENDED = "SUSPENDED", "Suspended"
    CANCELLED = "CANCELLED", "Cancelled"
    DELETED = "DELETED", "Deleted"


class DbStatus(models.TextChoices):
    PROVISIONING = "PROVISIONING", "Provisioning"
    READY = "READY", "Ready"
    MIGRATING = "MIGRATING", "Migrating"
    ERROR = "ERROR", "Error"
    ARCHIVED = "ARCHIVED", "Archived"


class DomainType(models.TextChoices):
    SUBDOMAIN = "SUBDOMAIN", "Subdomain"
    CUSTOM = "CUSTOM", "Custom Domain"


class BillingCycle(models.TextChoices):
    MONTHLY = "MONTHLY", "Monthly"
    YEARLY = "YEARLY", "Yearly"


class SubscriptionStatus(models.TextChoices):
    TRIALING = "TRIALING", "Trialing"
    ACTIVE = "ACTIVE", "Active"
    PAST_DUE = "PAST_DUE", "Past Due"
    CANCELLED = "CANCELLED", "Cancelled"


class InvoiceStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PAID = "PAID", "Paid"
    FAILED = "FAILED", "Failed"
    REFUNDED = "REFUNDED", "Refunded"


# ------------------------------------------------------------
# BASE MIXIN
# ------------------------------------------------------------

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ------------------------------------------------------------
# OWNERSHIP
# ------------------------------------------------------------

class CompanyOwner(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, blank=True, null=True)

    class Meta:
        db_table = "company_owners"

    def __str__(self):
        return f"{self.full_name} <{self.email}>"


# ------------------------------------------------------------
# CORE TENANT REGISTRY
# ------------------------------------------------------------

class Company(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org_id = models.PositiveBigIntegerField(
        default=generate_org_id,
        unique=True,
        editable=False,
        help_text="Public organization ID shared with the tenant database.",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32, blank=True, null=True)
    industry = models.CharField(max_length=100, blank=True, null=True)
    company_size = models.CharField(max_length=20, choices=CompanySize.choices, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    timezone = models.CharField(max_length=64, default="UTC")
    locale = models.CharField(max_length=16, default="en")
    currency = models.CharField(max_length=8, default="USD")
    status = models.CharField(max_length=20, choices=CompanyStatus.choices, default=CompanyStatus.TRIAL)
    logo_url = models.URLField(blank=True, null=True)
    owner = models.OneToOneField(CompanyOwner, on_delete=models.PROTECT, related_name="company")
    trial_ends_at = models.DateTimeField(blank=True, null=True)
    suspended_at = models.DateTimeField(blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)  # soft delete

    class Meta:
        db_table = "companies"
        indexes = [
            models.Index(fields=["org_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["slug"]),
        ]
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name


# ------------------------------------------------------------
# TENANT DATABASE ROUTING (the "database-per-tenant" part)
# ------------------------------------------------------------

class CompanyDatabase(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="database")
    provider = models.CharField(max_length=32, default="postgresql")
    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField(default=5432)
    database_name = models.CharField(max_length=128, help_text='e.g. "tenant_acme"')
    connection_url = models.TextField(help_text="Encrypt at rest in production")
    region = models.CharField(max_length=64, blank=True, null=True)
    schema_version = models.CharField(max_length=32, default="1.0.0")
    status = models.CharField(max_length=20, choices=DbStatus.choices, default=DbStatus.PROVISIONING)
    provisioned_at = models.DateTimeField(blank=True, null=True)
    last_migrated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "company_databases"

    def __str__(self):
        return f"{self.company.slug} -> {self.database_name}"


# ------------------------------------------------------------
# DOMAINS
# ------------------------------------------------------------

class CompanyDomain(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="domains")
    domain = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=20, choices=DomainType.choices, default=DomainType.SUBDOMAIN)
    is_verified = models.BooleanField(default=False)
    is_primary = models.BooleanField(default=True)

    class Meta:
        db_table = "company_domains"

    def __str__(self):
        return self.domain


# ------------------------------------------------------------
# SUBSCRIPTION / BILLING
# ------------------------------------------------------------

class Plan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)  # "Free", "Standard", ...
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2)
    max_users = models.PositiveIntegerField()
    max_storage_gb = models.PositiveIntegerField()
    features = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "plans"

    def __str__(self):
        return self.name


class CompanySubscription(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    billing_cycle = models.CharField(max_length=10, choices=BillingCycle.choices, default=BillingCycle.MONTHLY)
    seats = models.PositiveIntegerField(default=1)
    start_date = models.DateTimeField(auto_now_add=True)
    current_period_end = models.DateTimeField()
    cancel_at_period_end = models.BooleanField(default=False)
    status = models.CharField(max_length=20,choices=SubscriptionStatus.choices,default=SubscriptionStatus.TRIALING,)

    class Meta:
        db_table = "company_subscriptions"

    def __str__(self):
        return f"{self.company.slug} - {self.plan.name}"


class CompanyInvoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="invoices")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=8, default="USD")
    status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.PENDING)
    issued_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    invoice_url = models.URLField(blank=True, null=True)

    class Meta:
        db_table = "company_invoices"

    def __str__(self):
        return f"Invoice {self.id} - {self.company.slug}"


# ------------------------------------------------------------
# MODULES (Zoho-style: CRM, Books, Desk, People, etc.)
# ------------------------------------------------------------

class Module(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "modules"

    def __str__(self):
        return self.name


class CompanyModule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="modules")
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="companies")
    enabled_at = models.DateTimeField(auto_now_add=True)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "company_modules"
        unique_together = ("company", "module")

    def __str__(self):
        return f"{self.company.slug} - {self.module.code}"


# ------------------------------------------------------------
# AUDIT
# ------------------------------------------------------------

class CompanyAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="audit_logs")
    action = models.CharField(max_length=100, help_text='e.g. "company.suspended", "plan.upgraded"')
    performed_by = models.CharField(max_length=255, blank=True, null=True)
    metadata = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "company_audit_logs"
        indexes = [
            models.Index(fields=["company", "created_at"]),
        ]

    def __str__(self):
        return f"{self.company.slug} - {self.action}"
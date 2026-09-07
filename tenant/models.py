import uuid
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

# ------------------------------------------------------------
# COMPANY PROFILE (the deep business detail that only matters
# once you're "inside" the tenant)
# ------------------------------------------------------------

class CompanyProfile(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org_id = models.PositiveBigIntegerField(
        unique=True,
        editable=False,
        help_text="Public organization ID copied from the central company record.",
    )
    legal_name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    registration_no = models.CharField(max_length=100, blank=True, null=True)
    tax_id = models.CharField(max_length=100, blank=True, null=True)
    industry = models.CharField(max_length=100, blank=True, null=True)
    company_size = models.CharField(max_length=50, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    logo_url = models.URLField(blank=True, null=True)
    favicon_url = models.URLField(blank=True, null=True)

    # address
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)

    # localization
    timezone = models.CharField(max_length=64, default="UTC")
    locale = models.CharField(max_length=16, default="en")
    currency = models.CharField(max_length=8, default="NRP")
    date_format = models.CharField(max_length=20, default="DD/MM/YYYY")
    fiscal_year_start = models.CharField(max_length=5, default="04-01")

    class Meta:
        db_table = "company_profile"
        indexes = [models.Index(fields=["org_id"])]

    def __str__(self):
        return self.display_name


# ------------------------------------------------------------
# ORG STRUCTURE
# ------------------------------------------------------------

class Branch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_profile = models.ForeignKey(CompanyProfile, on_delete=models.CASCADE, related_name="branches")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    is_head_office = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "branches"

    def __str__(self):
        return self.name


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_profile = models.ForeignKey(CompanyProfile, on_delete=models.CASCADE, related_name="departments")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, related_name="departments",blank=True, null=True,)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True, null=True)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, related_name="children",blank=True, null=True,)
    head_user_id = models.UUIDField(blank=True, null=True,help_text="References a User in the app-level user table",)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "departments"

    def __str__(self):
        return self.name


# ------------------------------------------------------------
# SETTINGS (flexible key-value store — avoids a schema migration
# every time a new toggle is added)
# ------------------------------------------------------------

class CompanySetting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_profile = models.ForeignKey(CompanyProfile, on_delete=models.CASCADE, related_name="settings")
    category = models.CharField(max_length=100)  # "notifications", "security"...
    key = models.CharField(max_length=100)  # "invoice_prefix", "2fa_required"
    value = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "company_settings"
        unique_together = ("company_profile", "category", "key")

    def __str__(self):
        return f"{self.category}.{self.key}"


# ------------------------------------------------------------
# COMPANY-LEVEL DOCUMENTS (letterhead, seals, policy docs, etc.)
# ------------------------------------------------------------

class CompanyDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_profile = models.ForeignKey(CompanyProfile, on_delete=models.CASCADE, related_name="documents")
    type = models.CharField(max_length=50)  # "letterhead", "terms", "nda_template"
    name = models.CharField(max_length=255)
    file_url = models.URLField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "company_documents"

    def __str__(self):
        return self.name
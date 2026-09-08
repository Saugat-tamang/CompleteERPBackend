from rest_framework.routers import DefaultRouter

from .views import (
    CompanyDomainViewSet, CompanyFeatureViewSet, CompanySettingsViewSet,
    CompanyViewSet, IndustryViewSet, InvoiceViewSet, PlanFeatureViewSet,
    PlanViewSet, ProvisioningLogViewSet, SubscriptionViewSet, TenantDatabaseViewSet,
)

router = DefaultRouter()
router.register("industries", IndustryViewSet, basename="industry")
router.register("companies", CompanyViewSet, basename="company")
router.register("domains", CompanyDomainViewSet, basename="company-domain")
router.register("databases", TenantDatabaseViewSet, basename="tenant-database")
router.register("provisioning-logs", ProvisioningLogViewSet, basename="provisioning-log")
router.register("plans", PlanViewSet, basename="plan")
router.register("plan-features", PlanFeatureViewSet, basename="plan-feature")
router.register("subscriptions", SubscriptionViewSet, basename="subscription")
router.register("invoices", InvoiceViewSet, basename="invoice")
router.register("company-features", CompanyFeatureViewSet, basename="company-feature")
router.register("settings", CompanySettingsViewSet, basename="company-settings")

urlpatterns = router.urls

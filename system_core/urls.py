from rest_framework.routers import DefaultRouter

from .views import (
    ActivityLogViewSet, CountryViewSet, CurrencyViewSet, FeatureFlagViewSet,
    LanguageViewSet, SystemConfigViewSet, TimeZoneViewSet,
)

router = DefaultRouter()
router.register("countries", CountryViewSet, basename="country")
router.register("currencies", CurrencyViewSet, basename="currency")
router.register("languages", LanguageViewSet, basename="language")
router.register("timezones", TimeZoneViewSet, basename="timezone")
router.register("feature-flags", FeatureFlagViewSet, basename="feature-flag")
router.register("system-config", SystemConfigViewSet, basename="system-config")
router.register("activity-logs", ActivityLogViewSet, basename="activity-log")

urlpatterns = router.urls

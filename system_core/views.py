from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAdminUser

from .models import ActivityLog, Country, Currency, FeatureFlag, Language, SystemConfig, TimeZone


def model_serializer(model):
    meta = type("Meta", (), {"model": model, "fields": "__all__"})
    return type(f"{model.__name__}Serializer", (serializers.ModelSerializer,), {"Meta": meta})


class AdminModelViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]


class CountryViewSet(AdminModelViewSet):
    queryset, serializer_class = Country.objects.all(), model_serializer(Country)


class CurrencyViewSet(AdminModelViewSet):
    queryset, serializer_class = Currency.objects.all(), model_serializer(Currency)


class LanguageViewSet(AdminModelViewSet):
    queryset, serializer_class = Language.objects.all(), model_serializer(Language)


class TimeZoneViewSet(AdminModelViewSet):
    queryset, serializer_class = TimeZone.objects.all(), model_serializer(TimeZone)


class FeatureFlagViewSet(AdminModelViewSet):
    queryset, serializer_class = FeatureFlag.objects.all(), model_serializer(FeatureFlag)


class SystemConfigViewSet(AdminModelViewSet):
    queryset, serializer_class = SystemConfig.objects.all(), model_serializer(SystemConfig)


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminUser]
    queryset, serializer_class = ActivityLog.objects.all(), model_serializer(ActivityLog)

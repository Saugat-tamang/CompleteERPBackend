from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAdminUser

from .models import (
    Company, CompanyDomain, CompanyFeature, CompanySettings, Industry, Invoice,
    Plan, PlanFeature, ProvisioningLog, Subscription, TenantDatabase,
)


def model_serializer(model):
    meta = type("Meta", (), {"model": model, "fields": "__all__"})
    return type(f"{model.__name__}Serializer", (serializers.ModelSerializer,), {"Meta": meta})


class AdminModelViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]


class IndustryViewSet(AdminModelViewSet):
    queryset, serializer_class = Industry.objects.all(), model_serializer(Industry)


class CompanyViewSet(AdminModelViewSet):
    queryset, serializer_class = Company.all_objects.all(), model_serializer(Company)


class CompanyDomainViewSet(AdminModelViewSet):
    queryset, serializer_class = CompanyDomain.objects.all(), model_serializer(CompanyDomain)


class TenantDatabaseViewSet(AdminModelViewSet):
    queryset, serializer_class = TenantDatabase.objects.all(), model_serializer(TenantDatabase)


class ProvisioningLogViewSet(AdminModelViewSet):
    queryset, serializer_class = ProvisioningLog.objects.all(), model_serializer(ProvisioningLog)


class PlanViewSet(AdminModelViewSet):
    queryset, serializer_class = Plan.objects.all(), model_serializer(Plan)


class PlanFeatureViewSet(AdminModelViewSet):
    queryset, serializer_class = PlanFeature.objects.all(), model_serializer(PlanFeature)


class SubscriptionViewSet(AdminModelViewSet):
    queryset, serializer_class = Subscription.objects.all(), model_serializer(Subscription)


class InvoiceViewSet(AdminModelViewSet):
    queryset, serializer_class = Invoice.objects.all(), model_serializer(Invoice)


class CompanyFeatureViewSet(AdminModelViewSet):
    queryset, serializer_class = CompanyFeature.objects.all(), model_serializer(CompanyFeature)


class CompanySettingsViewSet(AdminModelViewSet):
    queryset, serializer_class = CompanySettings.objects.all(), model_serializer(CompanySettings)

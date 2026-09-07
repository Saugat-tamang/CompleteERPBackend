from django.http import Http404

from central.models import CompanyDomain, CompanyStatus
from Hatmasewa.db_router import (
    register_tenant_database,
    reset_current_tenant_database,
    set_current_tenant_database,
)


class TenantDatabaseMiddleware:
    """Resolve the request host to a verified company database."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin/"):
            return self.get_response(request)

        hostname = request.get_host().split(":", 1)[0].lower()
        domain = (
            CompanyDomain.objects.using("central")
            .select_related("company", "company__database")
            .filter(
                domain=hostname,
                is_verified=True,
                company__status__in=(CompanyStatus.TRIAL, CompanyStatus.ACTIVE),
            )
            .first()
        )
        if domain is None or domain.company.database.status != "READY":
            raise Http404("Company tenant was not found")

        alias = register_tenant_database(domain.company.database)
        token = set_current_tenant_database(alias)
        request.company = domain.company
        request.tenant_database_alias = alias
        try:
            return self.get_response(request)
        finally:
            reset_current_tenant_database(token)
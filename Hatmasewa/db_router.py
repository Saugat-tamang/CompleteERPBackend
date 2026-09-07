from contextvars import ContextVar
from urllib.parse import unquote, urlparse

from django.db import connections


_current_tenant_database = ContextVar("current_tenant_database", default=None)


def set_current_tenant_database(alias):
    """Select the tenant database alias for the current request or task."""
    return _current_tenant_database.set(alias)


def reset_current_tenant_database(token):
    _current_tenant_database.reset(token)


def get_current_tenant_database():
    return _current_tenant_database.get()


def tenant_database_alias(company):
    return f"tenant_{company.pk.hex}"


def register_tenant_database(company_database):
    """Register a tenant connection from its central database record."""
    alias = tenant_database_alias(company_database.company)
    parsed = urlparse(company_database.connection_url)
    scheme = parsed.scheme.split("+", 1)[0].lower()

    engine = {
        "mysql": "django.db.backends.mysql",
        "postgres": "django.db.backends.postgresql",
        "postgresql": "django.db.backends.postgresql",
        "sqlite": "django.db.backends.sqlite3",
    }.get(scheme)
    if engine is None:
        raise ValueError(f"Unsupported tenant database provider: {parsed.scheme}")

    database = {
        "ENGINE": engine,
        "NAME": unquote(parsed.path.lstrip("/")) or company_database.database_name,
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or company_database.host,
        "PORT": parsed.port or company_database.port,
        "CONN_MAX_AGE": 0,
    }
    if engine.endswith("sqlite3"):
        database = {"ENGINE": engine, "NAME": database["NAME"]}

    connections.databases[alias] = database
    return alias


class CentralTenantDatabaseRouter:
    central_app_label = "central"
    tenant_app_label = "tenant"
    central_database = "central"

    def db_for_read(self, model, **hints):
        if model._meta.app_label == self.central_app_label:
            return self.central_database
        if model._meta.app_label == self.tenant_app_label:
            alias = get_current_tenant_database()
            if alias is None:
                raise RuntimeError("Tenant database is not selected for this request")
            return alias
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == self.central_app_label:
            return self.central_database
        if model._meta.app_label == self.tenant_app_label:
            alias = get_current_tenant_database()
            if alias is None:
                raise RuntimeError("Tenant database is not selected for this request")
            return alias
        return None

    def allow_relation(self, obj1, obj2, **hints):
        app_labels = {obj1._meta.app_label, obj2._meta.app_label}
        if self.central_app_label in app_labels or self.tenant_app_label in app_labels:
            return app_labels == {self.central_app_label} or app_labels == {self.tenant_app_label}
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == self.central_app_label:
            return db == self.central_database
        if app_label == self.tenant_app_label:
            return db.startswith("tenant_")
        if db == self.central_database:
            return False
        return None
"""graphene_django_observability — Django app declaration."""

from importlib import metadata

from django.apps import AppConfig

__version__ = metadata.version(__name__)


class GrapheneDjangoObservabilityConfig(AppConfig):
    """Django AppConfig for graphene_django_observability.

    Add this app to ``INSTALLED_APPS`` and register the Django HTTP
    middleware in ``MIDDLEWARE`` in your ``settings.py``::

        INSTALLED_APPS = [
            ...
            "graphene_django_observability",
        ]

        MIDDLEWARE = [
            ...
            "graphene_django_observability.django_middleware.GraphQLObservabilityDjangoMiddleware",
        ]

    Then enable the Graphene middleware in your ``GRAPHENE`` settings::

        GRAPHENE = {
            "SCHEMA": "myapp.schema.schema",
            "MIDDLEWARE": [
                "graphene_django_observability.middleware.PrometheusMiddleware",
                # optional:
                "graphene_django_observability.logging_middleware.GraphQLQueryLoggingMiddleware",
            ],
        }

    Configure the library via ``GRAPHENE_OBSERVABILITY`` in ``settings.py``::

        GRAPHENE_OBSERVABILITY = {
            "graphql_metrics_enabled": True,
            "track_query_depth": True,
            "track_query_complexity": True,
            "track_field_resolution": False,
            "track_per_user": True,
            "query_logging_enabled": False,
            "log_query_body": False,
            "log_query_variables": False,
            # Override the paths that trigger instrumentation (default: ["/graphql/"]):
            "graphql_paths": ["/graphql/"],
        }
    """

    name = "graphene_django_observability"
    verbose_name = "GraphQL Observability"
    default_auto_field = "django.db.models.BigAutoField"


config = GrapheneDjangoObservabilityConfig  # pylint: disable=invalid-name

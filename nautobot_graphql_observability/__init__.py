"""App declaration for nautobot_graphql_observability.

This module provides two Django AppConfig subclasses:

- :class:`NautobotAppGraphqlObservabilityConfig` — used when Nautobot is
  installed.  It inherits from ``NautobotAppConfig`` and patches
  Nautobot's ``GraphQLDRFAPIView`` so that the Graphene middleware
  configured in ``GRAPHENE["MIDDLEWARE"]`` is loaded for the DRF-based
  ``/api/graphql/`` endpoint.

- :class:`GraphqlObservabilityConfig` — used in plain Django projects
  (without Nautobot).  It inherits from Django's standard ``AppConfig``
  and registers the Django HTTP middleware via ``MIDDLEWARE`` in
  ``settings.py``.

The active config is exported as ``config`` and is picked up by
``default_app_config`` / ``AppConfig.name``.
"""

from importlib import metadata

__version__ = metadata.version(__name__)

# ---------------------------------------------------------------------------
# Shared defaults used by both config classes and by _get_app_settings()
# ---------------------------------------------------------------------------

_DEFAULT_SETTINGS = {
    "graphql_metrics_enabled": True,
    "track_query_depth": True,
    "track_query_complexity": True,
    "track_field_resolution": False,
    "track_per_user": True,
    "query_logging_enabled": False,
    "log_query_body": False,
    "log_query_variables": False,
}

# ---------------------------------------------------------------------------
# Try the Nautobot-specific config first; fall back to plain Django AppConfig
# ---------------------------------------------------------------------------

try:
    from nautobot.apps import NautobotAppConfig  # noqa: F401

    class NautobotAppGraphqlObservabilityConfig(NautobotAppConfig):
        """App configuration for use as a Nautobot plugin.

        Registers the Django HTTP middleware automatically (via the
        Nautobot ``middleware`` attribute) and patches
        ``GraphQLDRFAPIView.init_graphql()`` so that Graphene middleware
        listed in ``GRAPHENE["MIDDLEWARE"]`` is loaded for the DRF
        ``/api/graphql/`` endpoint.
        """

        name = "nautobot_graphql_observability"
        verbose_name = "GraphQL Observability"
        version = __version__
        author = "Lydien SANDANASAMY"
        description = (
            "Generic Graphene-Django middleware for GraphQL observability "
            "via Prometheus metrics and structured query logging."
        )
        base_url = "nautobot-graphql-observability"
        required_settings = []
        default_settings = _DEFAULT_SETTINGS
        middleware = [
            "nautobot_graphql_observability.django_middleware.GraphQLObservabilityDjangoMiddleware",
        ]
        docs_view_name = "plugins:nautobot_graphql_observability:docs"
        searchable_models = []

        def ready(self):
            """Patch Nautobot's GraphQLDRFAPIView to load Graphene middleware from settings.

            Nautobot's ``GraphQLDRFAPIView.init_graphql()`` does not load middleware
            from ``GRAPHENE["MIDDLEWARE"]`` when ``self.middleware`` is ``None`` (the
            default).  This is a known limitation of the DRF-based GraphQL view —
            the standard ``graphene_django.views.GraphQLView`` (used by the GraphiQL
            UI at ``/graphql/``) loads middleware correctly.

            No official extension point (``override_views``, etc.) can replace this
            patch because the ``graphql-api`` URL is registered without a namespace.
            Request duration and query logging are handled by
            :class:`~nautobot_graphql_observability.django_middleware.GraphQLObservabilityDjangoMiddleware`,
            which is registered via :attr:`middleware` (the official Nautobot mechanism).
            """
            super().ready()
            self._patch_init_graphql()

        @staticmethod
        def _patch_init_graphql():
            """Patch ``GraphQLDRFAPIView.init_graphql`` to load ``GRAPHENE["MIDDLEWARE"]``."""
            from nautobot.core.api.views import GraphQLDRFAPIView  # pylint: disable=import-outside-toplevel

            original_init_graphql = GraphQLDRFAPIView.init_graphql

            def patched_init_graphql(view_self):
                original_init_graphql(view_self)
                if view_self.middleware is None:
                    from graphene_django.settings import graphene_settings  # pylint: disable=import-outside-toplevel
                    from graphene_django.views import instantiate_middleware  # pylint: disable=import-outside-toplevel

                    if graphene_settings.MIDDLEWARE:
                        view_self.middleware = list(instantiate_middleware(graphene_settings.MIDDLEWARE))

            GraphQLDRFAPIView.init_graphql = patched_init_graphql

    config = NautobotAppGraphqlObservabilityConfig  # pylint: disable=invalid-name

except ImportError:
    # Nautobot is not installed — use a plain Django AppConfig.
    from django.apps import AppConfig

    class GraphqlObservabilityConfig(AppConfig):
        """App configuration for use in plain Django projects (without Nautobot).

        To register the Django HTTP middleware automatically, add it to
        ``MIDDLEWARE`` in ``settings.py``::

            MIDDLEWARE = [
                ...
                "nautobot_graphql_observability.django_middleware.GraphQLObservabilityDjangoMiddleware",
            ]

        Configure the middleware via ``GRAPHENE_OBSERVABILITY`` in
        ``settings.py``::

            GRAPHENE_OBSERVABILITY = {
                "graphql_metrics_enabled": True,
                "track_query_depth": True,
                "track_query_complexity": True,
                "track_field_resolution": False,
                "track_per_user": True,
                "query_logging_enabled": False,
                "log_query_body": False,
                "log_query_variables": False,
                # Paths that trigger GraphQL instrumentation (default shown):
                "graphql_paths": ["/graphql/", "/api/graphql/"],
            }
        """

        name = "nautobot_graphql_observability"
        verbose_name = "GraphQL Observability"
        default_auto_field = "django.db.models.BigAutoField"

    config = GraphqlObservabilityConfig  # pylint: disable=invalid-name

"""App declaration for nautobot_app_graphql_observability."""

# Metadata is inherited from Nautobot. If not including Nautobot in the environment, this should be added
from importlib import metadata

from nautobot.apps import NautobotAppConfig

__version__ = metadata.version(__name__)


class NautobotAppGraphqlObservabilityConfig(NautobotAppConfig):
    """App configuration for the nautobot_app_graphql_observability app."""

    name = "nautobot_app_graphql_observability"
    verbose_name = "Nautobot App GraphQL Observability"
    version = __version__
    author = "Lydien SANDANASAMY"
    description = "Nautobot App GraphQL Observability."
    base_url = "nautobot-app-graphql-observability"
    required_settings = []
    default_settings = {
        "graphql_metrics_enabled": True,
        "track_query_depth": True,
        "track_query_complexity": True,
        "track_field_resolution": False,
        "track_per_user": True,
        "query_logging_enabled": False,
        "log_query_body": False,
        "log_query_variables": False,
    }
    docs_view_name = "plugins:nautobot_app_graphql_observability:docs"
    searchable_models = []

    def ready(self):
        """Patch Nautobot's GraphQLDRFAPIView to load Graphene middleware and measure real request duration.

        Nautobot's GraphQLDRFAPIView.init_graphql() does not load middleware from
        GRAPHENE["MIDDLEWARE"] when self.middleware is None (the default). This patch
        ensures that middleware configured in Django settings is properly loaded.

        Also patches ``post()`` so that the duration recorded by Prometheus and
        query logging reflects the full HTTP request, not just root-field resolution.
        """
        super().ready()
        self._patch_graphql_view()

    @staticmethod
    def _patch_graphql_view():
        """Monkey-patch GraphQLDRFAPIView to load middleware and measure full request duration."""
        import time  # pylint: disable=import-outside-toplevel

        from nautobot.core.api.views import GraphQLDRFAPIView  # pylint: disable=import-outside-toplevel

        # --- Patch init_graphql to load middleware from settings ---
        original_init_graphql = GraphQLDRFAPIView.init_graphql

        def patched_init_graphql(view_self):
            original_init_graphql(view_self)
            if view_self.middleware is None:
                from graphene_django.settings import graphene_settings  # pylint: disable=import-outside-toplevel
                from graphene_django.views import instantiate_middleware  # pylint: disable=import-outside-toplevel

                if graphene_settings.MIDDLEWARE:
                    view_self.middleware = list(instantiate_middleware(graphene_settings.MIDDLEWARE))

        GraphQLDRFAPIView.init_graphql = patched_init_graphql

        # --- Patch post() to record real total request duration ---
        import functools  # pylint: disable=import-outside-toplevel

        original_post = GraphQLDRFAPIView.post

        @functools.wraps(original_post)
        def patched_post(view_self, request, *args, **kwargs):
            start_time = time.monotonic()
            response = original_post(view_self, request, *args, **kwargs)
            duration = time.monotonic() - start_time

            from nautobot_app_graphql_observability.logging_middleware import (  # pylint: disable=import-outside-toplevel
                _REQUEST_ATTR as _LOGGING_ATTR,
            )
            from nautobot_app_graphql_observability.logging_middleware import (
                _emit_log,
            )
            from nautobot_app_graphql_observability.metrics import (  # pylint: disable=import-outside-toplevel
                graphql_request_duration_seconds,
            )
            from nautobot_app_graphql_observability.middleware import (  # pylint: disable=import-outside-toplevel
                _REQUEST_ATTR as _PROM_ATTR,
            )

            # Record Prometheus duration histogram
            prom_meta = getattr(request, _PROM_ATTR, None)
            if prom_meta is not None:
                graphql_request_duration_seconds.labels(
                    operation_type=prom_meta["operation_type"],
                    operation_name=prom_meta["operation_name"],
                ).observe(duration)

            # Emit query log with real duration
            log_meta = getattr(request, _LOGGING_ATTR, None)
            if log_meta is not None:
                _emit_log(log_meta, duration * 1000)

            return response

        GraphQLDRFAPIView.post = patched_post


config = NautobotAppGraphqlObservabilityConfig  # pylint:disable=invalid-name

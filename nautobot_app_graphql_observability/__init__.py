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
        """Monkey-patch GraphQL views to load middleware and measure full request duration.

        Patches two views:

        1. ``GraphQLDRFAPIView`` – the DRF-based REST API endpoint (``/api/graphql/``).
           Its ``init_graphql()`` does not load ``GRAPHENE["MIDDLEWARE"]`` when
           ``self.middleware`` is ``None``, so we patch it to do so.  We also wrap
           ``post()`` to record real request duration.

        2. ``CustomGraphQLView`` – the GraphiQL UI endpoint (``/graphql/``).
           It inherits from ``graphene_django.views.GraphQLView`` which already
           loads middleware from settings, but its ``dispatch()`` must be wrapped
           to record duration and emit logs.
        """
        import functools  # pylint: disable=import-outside-toplevel
        import time  # pylint: disable=import-outside-toplevel

        from nautobot.core.api.views import GraphQLDRFAPIView  # pylint: disable=import-outside-toplevel
        from nautobot.core.views import CustomGraphQLView  # pylint: disable=import-outside-toplevel

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

        # --- Shared helper: record metrics and emit log after a request ---
        def _record_observability(request, duration):
            """Record Prometheus duration histogram and emit query log."""
            from nautobot_app_graphql_observability.logging_middleware import (  # noqa: I001  # pylint: disable=import-outside-toplevel
                _REQUEST_ATTR as _LOGGING_ATTR,
                _emit_log,
            )
            from nautobot_app_graphql_observability.metrics import (  # pylint: disable=import-outside-toplevel
                graphql_request_duration_seconds,
            )
            from nautobot_app_graphql_observability.middleware import (  # pylint: disable=import-outside-toplevel
                _REQUEST_ATTR as _PROM_ATTR,
            )

            prom_meta = getattr(request, _PROM_ATTR, None)
            if prom_meta is not None:
                graphql_request_duration_seconds.labels(
                    operation_type=prom_meta["operation_type"],
                    operation_name=prom_meta["operation_name"],
                ).observe(duration)

            log_meta = getattr(request, _LOGGING_ATTR, None)
            if log_meta is not None:
                _emit_log(log_meta, duration * 1000)

        # --- Patch GraphQLDRFAPIView.post() (REST API: /api/graphql/) ---
        original_post = GraphQLDRFAPIView.post

        @functools.wraps(original_post)
        def patched_post(view_self, request, *args, **kwargs):
            start_time = time.monotonic()
            response = original_post(view_self, request, *args, **kwargs)
            duration = time.monotonic() - start_time
            _record_observability(request, duration)
            return response

        GraphQLDRFAPIView.post = patched_post

        # --- Patch CustomGraphQLView.dispatch() (GraphiQL UI: /graphql/) ---
        original_dispatch = CustomGraphQLView.dispatch

        @functools.wraps(original_dispatch)
        def patched_dispatch(view_self, request, *args, **kwargs):
            start_time = time.monotonic()
            response = original_dispatch(view_self, request, *args, **kwargs)
            duration = time.monotonic() - start_time
            _record_observability(request, duration)
            return response

        CustomGraphQLView.dispatch = patched_dispatch


config = NautobotAppGraphqlObservabilityConfig  # pylint:disable=invalid-name

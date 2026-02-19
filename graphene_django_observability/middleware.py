"""Graphene middleware for exporting Prometheus metrics from GraphQL queries."""

import time

from graphql import GraphQLResolveInfo
from graphql.language.ast import FieldNode

from graphene_django_observability.metrics import (
    graphql_errors_total,
    graphql_field_resolution_duration_seconds,
    graphql_query_complexity,
    graphql_query_depth,
    graphql_requests_by_user_total,
    graphql_requests_total,
)
from graphene_django_observability.utils import (
    calculate_query_complexity,
    calculate_query_depth,
    stash_meta_on_request,
)

# Key used to stash Prometheus metadata on the request for the Django middleware.
_REQUEST_ATTR = "_graphql_prometheus_meta"

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


def _get_app_settings():
    """Load observability settings from ``settings.GRAPHENE_OBSERVABILITY``.

    Falls back to built-in defaults for any key not present in the dict.

    Returns:
        dict: Resolved settings merged with defaults.
    """
    from django.conf import settings  # pylint: disable=import-outside-toplevel

    user_config = getattr(settings, "GRAPHENE_OBSERVABILITY", {})
    return {**_DEFAULT_SETTINGS, **user_config}


class PrometheusMiddleware:  # pylint: disable=too-few-public-methods
    """Graphene middleware that instruments GraphQL resolvers with Prometheus metrics.

    On root-level resolutions, records counters and advanced metrics immediately
    (these are not timing-sensitive) and stashes operation labels onto the
    request so that :class:`GraphQLObservabilityDjangoMiddleware` can record
    the duration histogram after the full HTTP response is built.

    Optionally records advanced metrics based on ``GRAPHENE_OBSERVABILITY``:

    - ``track_query_depth``: Record query nesting depth histogram.
    - ``track_query_complexity``: Record query field count histogram.
    - ``track_field_resolution``: Record per-field resolver duration histogram.
    - ``track_per_user``: Record per-user request counter.

    Usage in Django settings::

        GRAPHENE = {
            "MIDDLEWARE": [
                "graphene_django_observability.middleware.PrometheusMiddleware",
            ]
        }
    """

    def resolve(self, next: callable, root: object, info: GraphQLResolveInfo, **kwargs: object) -> object:  # pylint: disable=redefined-builtin
        """Intercept each field resolution and record metrics.

        Root-level resolutions (root is None) record counters and advanced
        metrics and stash labels for the Django middleware to record duration.
        Nested resolutions optionally record per-field duration when enabled.

        Args:
            next (callable): Callable to continue the resolution chain.
            root (object): Parent resolved value. None for top-level fields.
            info (GraphQLResolveInfo): GraphQL resolve info containing operation metadata.
            **kwargs (object): Field arguments.

        Returns:
            object: The result of the resolver.
        """
        config = _get_app_settings()

        if root is not None:
            if config.get("track_field_resolution", False):
                return self._resolve_field_with_metrics(next, root, info, **kwargs)
            return next(root, info, **kwargs)

        operation_type = info.operation.operation.value
        operation_name = self._get_operation_name(info)

        # Stash labels on the request (only for the first root field) so
        # the Django middleware can record the full-request duration.
        # For DRF views, info.context is a DRF Request wrapping a WSGIRequest.
        # The Django middleware sees the WSGIRequest, so stash on both.
        request = info.context
        if not hasattr(request, _REQUEST_ATTR):
            meta = {
                "operation_type": operation_type,
                "operation_name": operation_name,
            }
            stash_meta_on_request(request, _REQUEST_ATTR, meta)

        try:
            result = next(root, info, **kwargs)
            return result
        except Exception as error:
            graphql_errors_total.labels(
                operation_type=operation_type,
                operation_name=operation_name,
                error_type=type(error).__name__,
            ).inc()
            # Mark the error on the stashed metadata so the Django middleware
            # records the correct status.
            meta = getattr(request, _REQUEST_ATTR, None)
            if meta is not None:
                meta["error"] = True
            raise
        finally:
            # Counters and advanced metrics are not timing-sensitive, record now.
            status = "error" if getattr(request, _REQUEST_ATTR, {}).get("error") else "success"

            graphql_requests_total.labels(
                operation_type=operation_type,
                operation_name=operation_name,
                status=status,
            ).inc()

            self._record_advanced_metrics(info, operation_name, config)

    @staticmethod
    def _resolve_field_with_metrics(next, root, info, **kwargs):  # pylint: disable=redefined-builtin
        """Resolve a nested field while recording per-field duration."""
        type_name = info.parent_type.name if info.parent_type else "Unknown"
        field_name = info.field_name

        start_time = time.monotonic()
        try:
            return next(root, info, **kwargs)
        finally:
            duration = time.monotonic() - start_time
            graphql_field_resolution_duration_seconds.labels(
                type_name=type_name,
                field_name=field_name,
            ).observe(duration)

    @staticmethod
    def _record_advanced_metrics(info, operation_name, config):
        """Record query depth, complexity, and per-user metrics if enabled."""
        if config.get("track_query_depth", True):
            depth = calculate_query_depth(info.operation.selection_set, info.fragments)
            graphql_query_depth.labels(operation_name=operation_name).observe(depth)

        if config.get("track_query_complexity", True):
            complexity = calculate_query_complexity(info.operation.selection_set, info.fragments)
            graphql_query_complexity.labels(operation_name=operation_name).observe(complexity)

        if config.get("track_per_user", True):
            user = "anonymous"
            request = info.context
            if hasattr(request, "user") and hasattr(request.user, "is_authenticated"):
                if request.user.is_authenticated:
                    user = request.user.username
            graphql_requests_by_user_total.labels(
                user=user,
                operation_type=info.operation.operation.value,
                operation_name=operation_name,
            ).inc()

    @staticmethod
    def _get_operation_name(info: GraphQLResolveInfo) -> str:
        """Extract the operation name from the GraphQL query.

        Uses the explicit operation name if provided, otherwise falls back
        to the sorted, comma-joined root field names (e.g. "devices,locations").
        """
        if info.operation.name:
            return info.operation.name.value
        root_fields = []
        if info.operation.selection_set:
            for selection in info.operation.selection_set.selections:
                if isinstance(selection, FieldNode):
                    root_fields.append(selection.name.value)
        return ",".join(sorted(root_fields)) if root_fields else "anonymous"

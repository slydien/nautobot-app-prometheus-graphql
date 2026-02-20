"""Django HTTP middleware for recording GraphQL request duration and emitting query logs.

This middleware wraps HTTP requests to GraphQL endpoints, measuring the full
request duration and then reading metadata stashed by the Graphene-level
middlewares (:class:`~graphene_django_observability.middleware.PrometheusMiddleware`
and :class:`~graphene_django_observability.logging_middleware.GraphQLQueryLoggingMiddleware`)
to record Prometheus histograms and emit structured log lines.

Add it to ``MIDDLEWARE`` in ``settings.py``::

    MIDDLEWARE = [
        ...
        "graphene_django_observability.django_middleware.GraphQLObservabilityDjangoMiddleware",
    ]

The set of paths that trigger instrumentation defaults to ``{"/graphql/"}``
and can be overridden via the ``graphql_paths`` key in ``GRAPHENE_OBSERVABILITY``.
"""

import time

# Default path when no custom configuration is provided.
_DEFAULT_GRAPHQL_PATHS = frozenset(("/graphql/",))


def _record_observability(request, duration):
    """Read stashed metadata from the request and record metrics / emit logs.

    Args:
        request: The Django/DRF request object.
        duration: Wall-clock duration of the request in seconds.
    """
    from graphene_django_observability.logging_middleware import (  # noqa: I001  # pylint: disable=import-outside-toplevel
        _REQUEST_ATTR as _LOGGING_ATTR,
        _emit_log,
    )
    from graphene_django_observability.metrics import (  # pylint: disable=import-outside-toplevel
        graphql_request_duration_seconds,
    )
    from graphene_django_observability.middleware import (  # pylint: disable=import-outside-toplevel
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


class GraphQLObservabilityDjangoMiddleware:  # pylint: disable=too-few-public-methods
    """Django middleware that measures full GraphQL request duration.

    For non-GraphQL requests this middleware is a no-op pass-through.

    On GraphQL paths it:

    1. Records wall-clock time around the downstream middleware / view chain.
    2. After the response is built, reads metadata stashed on the request by
       the Graphene middlewares and records a Prometheus duration histogram
       and emits a structured query log line.

    The set of paths treated as GraphQL endpoints is resolved at startup from
    ``GRAPHENE_OBSERVABILITY["graphql_paths"]``.  Defaults to ``{"/graphql/"}``.
    """

    def __init__(self, get_response):
        """Initialize the middleware and resolve the GraphQL path set."""
        self.get_response = get_response
        self._graphql_paths = self._resolve_graphql_paths()

    @staticmethod
    def _resolve_graphql_paths():
        """Build the frozenset of paths that should be instrumented.

        Reads the ``graphql_paths`` key from ``GRAPHENE_OBSERVABILITY``.
        Falls back to :data:`_DEFAULT_GRAPHQL_PATHS` when absent or empty.

        Returns:
            frozenset[str]: The set of URL paths to instrument.
        """
        from graphene_django_observability.middleware import (
            _get_app_settings,  # pylint: disable=import-outside-toplevel
        )

        config = _get_app_settings()
        custom_paths = config.get("graphql_paths")
        if custom_paths:
            return frozenset(custom_paths)
        return _DEFAULT_GRAPHQL_PATHS

    def __call__(self, request):
        """Wrap GraphQL requests with timing; pass through everything else."""
        if request.path not in self._graphql_paths:
            return self.get_response(request)

        start_time = time.monotonic()
        response = self.get_response(request)
        duration = time.monotonic() - start_time

        _record_observability(request, duration)

        return response

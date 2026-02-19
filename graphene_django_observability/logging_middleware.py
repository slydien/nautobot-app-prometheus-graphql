"""Graphene middleware for logging GraphQL queries via Python's logging module."""

import json
import logging

from graphql import GraphQLResolveInfo

from graphene_django_observability.middleware import PrometheusMiddleware, _get_app_settings
from graphene_django_observability.utils import stash_meta_on_request

LOGGER_NAME = "graphene_django_observability.graphql_query_log"
_LOGGER_CONFIGURED = False

# Key used to stash GraphQL metadata on the request for the Django middleware.
_REQUEST_ATTR = "_graphql_logging_meta"


def _get_logger():
    """Return the query log logger, ensuring it has a handler.

    Deferred setup avoids being overwritten by Django's ``dictConfig``
    which runs during ``django.setup()``.
    """
    global _LOGGER_CONFIGURED  # noqa: PLW0603  # pylint: disable=global-statement
    log = logging.getLogger(LOGGER_NAME)
    if not _LOGGER_CONFIGURED:
        _LOGGER_CONFIGURED = True
        if not log.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s.%(msecs)03d %(levelname)-7s %(name)s : %(message)s",
                    datefmt="%H:%M:%S",
                )
            )
            log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log


class GraphQLQueryLoggingMiddleware:  # pylint: disable=too-few-public-methods
    """Graphene middleware that captures GraphQL query metadata for logging.

    On root-level resolutions, stashes operation metadata onto the request so
    that :class:`GraphQLObservabilityDjangoMiddleware` can emit a log entry
    with the **real** total request duration after the full response is built.

    Controlled by ``GRAPHENE_OBSERVABILITY``:

    - ``query_logging_enabled``: Master switch (default: False).
    - ``log_query_body``: Include the full query text (default: False).
    - ``log_query_variables``: Include query variables (default: False).

    Usage in Django settings::

        GRAPHENE = {
            "MIDDLEWARE": [
                "graphene_django_observability.logging_middleware.GraphQLQueryLoggingMiddleware",
                "graphene_django_observability.middleware.PrometheusMiddleware",
            ]
        }
    """

    def resolve(self, next: callable, root: object, info: GraphQLResolveInfo, **kwargs: object) -> object:  # pylint: disable=redefined-builtin
        """Intercept root-level resolutions and stash metadata on the request.

        Args:
            next (callable): Callable to continue the resolution chain.
            root (object): Parent resolved value. None for top-level fields.
            info (GraphQLResolveInfo): GraphQL resolve info containing operation metadata.
            **kwargs (object): Field arguments.

        Returns:
            object: The result of the resolver.
        """
        if root is not None:
            return next(root, info, **kwargs)

        config = _get_app_settings()
        if not config.get("query_logging_enabled", False):
            return next(root, info, **kwargs)

        # Stash metadata on the request (only for the first root field).
        # For DRF views, info.context is a DRF Request wrapping a WSGIRequest.
        # The Django middleware sees the WSGIRequest, so stash on both.
        request = info.context
        if not hasattr(request, _REQUEST_ATTR):
            meta = {
                "operation_type": info.operation.operation.value,
                "operation_name": PrometheusMiddleware._get_operation_name(info),
                "user": self._get_user(info),
                "config": config,
            }

            if config.get("log_query_body", False):
                meta["query_body"] = _extract_query_body(info)

            if config.get("log_query_variables", False):
                meta["variables"] = _extract_variables(info)

            stash_meta_on_request(request, _REQUEST_ATTR, meta)

        try:
            return next(root, info, **kwargs)
        except Exception as error:
            # Record the error on the stashed metadata so the Django
            # middleware can log it.
            meta = getattr(request, _REQUEST_ATTR, None)
            if meta is not None:
                meta["error"] = error
            raise

    @staticmethod
    def _get_user(info):
        """Extract the username from the request context."""
        request = info.context
        if hasattr(request, "user") and hasattr(request.user, "is_authenticated"):
            if request.user.is_authenticated:
                return request.user.username
        return "anonymous"


def _emit_log(meta, duration_ms):
    """Emit a structured log record for the GraphQL query."""
    error = meta.get("error")
    status = "error" if error else "success"

    extra = {
        "operation_type": meta["operation_type"],
        "operation_name": meta["operation_name"],
        "user": meta["user"],
        "duration_ms": round(duration_ms, 1),
        "status": status,
    }
    if error:
        extra["error_type"] = type(error).__name__
    if meta.get("query_body"):
        extra["query"] = meta["query_body"]
    if meta.get("variables"):
        extra["variables"] = meta["variables"]

    log = _get_logger()
    if error:
        log.warning("graphql_query", extra=extra)
    else:
        log.info("graphql_query", extra=extra)


def _extract_query_body(info):
    """Extract the GraphQL query text from the parsed AST.

    Reads ``info.operation.loc.source.body`` which is always available after
    graphql-core has parsed the query, regardless of the request content type
    (``application/json``, ``application/graphql``, etc.).

    Returns:
        str or None: The query string, or None if not available.
    """
    try:
        source_body = info.operation.loc.source.body
        if source_body:
            return source_body.replace("\n", " ").strip()
    except Exception:  # noqa: S110  # pylint: disable=broad-except
        pass
    return None


def _extract_variables(info):
    """Extract GraphQL query variables from the resolved execution context.

    Reads ``info.variable_values`` which is populated by graphql-core from
    the parsed request regardless of the content type.

    Returns:
        str or None: JSON-encoded variables, or None if not available.
    """
    try:
        variables = info.variable_values
        if variables:
            return json.dumps(variables, separators=(",", ":"))
    except Exception:  # noqa: S110  # pylint: disable=broad-except
        pass
    return None

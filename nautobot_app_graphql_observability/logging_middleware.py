"""Graphene middleware for logging GraphQL queries via Python's logging module."""

import json
import logging
import time

from graphql import GraphQLResolveInfo

from nautobot_app_graphql_observability.middleware import PrometheusMiddleware, _get_app_settings

LOGGER_NAME = "nautobot_app_graphql_observability.graphql_query_log"
_logger_configured = False


def _get_logger():
    """Return the query log logger, ensuring it has a handler.

    Deferred setup avoids being overwritten by Django's ``dictConfig``
    which runs during ``django.setup()``.
    """
    global _logger_configured  # noqa: PLW0603  # pylint: disable=global-statement
    log = logging.getLogger(LOGGER_NAME)
    if not _logger_configured:
        _logger_configured = True
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
    """Graphene middleware that logs GraphQL query execution details.

    Logs operation metadata (type, name, user, duration, status) at the root
    resolver level using Python's ``logging`` module. Users can route these
    logs to any backend via Django's ``LOGGING`` configuration.

    Controlled by app settings:

    - ``query_logging_enabled``: Master switch (default: False).
    - ``log_query_body``: Include the full query text (default: False).
    - ``log_query_variables``: Include query variables (default: False).

    Usage in Django settings::

        GRAPHENE = {
            "MIDDLEWARE": [
                "nautobot_app_graphql_observability.logging_middleware.GraphQLQueryLoggingMiddleware",
                "nautobot_app_graphql_observability.middleware.PrometheusMiddleware",
            ]
        }
    """

    def resolve(self, next: callable, root: object, info: GraphQLResolveInfo, **kwargs: object) -> object:  # pylint: disable=redefined-builtin
        """Intercept root-level resolutions and log query details.

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

        operation_type = info.operation.operation.value
        operation_name = PrometheusMiddleware._get_operation_name(info)
        user = self._get_user(info)
        start_time = time.monotonic()

        try:
            result = next(root, info, **kwargs)
            self._log_query(config, operation_type, operation_name, user, start_time, info)
            return result
        except Exception as error:
            self._log_query(config, operation_type, operation_name, user, start_time, info, error=error)
            raise

    @staticmethod
    def _get_user(info):
        """Extract the username from the request context."""
        request = info.context
        if hasattr(request, "user") and hasattr(request.user, "is_authenticated"):
            if request.user.is_authenticated:
                return request.user.username
        return "anonymous"

    @staticmethod
    def _log_query(config, operation_type, operation_name, user, start_time, info, error=None):
        """Emit a structured log entry for the GraphQL query."""
        duration_ms = (time.monotonic() - start_time) * 1000
        status = "error" if error else "success"

        parts = [
            f"operation_type={operation_type}",
            f"operation_name={operation_name}",
            f"user={user}",
            f"duration_ms={duration_ms:.1f}",
            f"status={status}",
        ]

        if error:
            parts.append(f"error_type={type(error).__name__}")

        if config.get("log_query_body", False):
            query_text = _extract_query_body(info)
            if query_text:
                parts.append(f"query={query_text}")

        if config.get("log_query_variables", False):
            variables = _extract_variables(info)
            if variables:
                parts.append(f"variables={variables}")

        message = " ".join(parts)
        log = _get_logger()

        if error:
            log.warning(message)
        else:
            log.info(message)


def _extract_query_body(info):
    """Extract the GraphQL query text from the request body.

    Uses ``request.data`` (already parsed by DRF) instead of ``request.body``
    to avoid ``RawPostDataException`` when the stream has been consumed.

    Returns:
        str or None: The query string, or None if not available.
    """
    request = info.context
    try:
        data = getattr(request, "data", None) or {}
        query = data.get("query", "")
        if query:
            return query.replace("\n", " ").strip()
    except Exception:  # noqa: S110  # pylint: disable=broad-except
        pass
    return None


def _extract_variables(info):
    """Extract GraphQL query variables from the request body.

    Uses ``request.data`` (already parsed by DRF) instead of ``request.body``
    to avoid ``RawPostDataException`` when the stream has been consumed.

    Returns:
        str or None: JSON-encoded variables, or None if not available.
    """
    request = info.context
    try:
        data = getattr(request, "data", None) or {}
        variables = data.get("variables")
        if variables:
            return json.dumps(variables, separators=(",", ":"))
    except Exception:  # noqa: S110  # pylint: disable=broad-except
        pass
    return None

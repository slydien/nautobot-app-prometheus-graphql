"""Graphene middleware for logging GraphQL queries via Python's logging module."""

import json
import logging

from graphql import GraphQLResolveInfo

from nautobot_app_graphql_observability.middleware import PrometheusMiddleware, _get_app_settings

LOGGER_NAME = "nautobot_app_graphql_observability.graphql_query_log"
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
    that :class:`GraphQLQueryLoggingDjangoMiddleware` can emit a log entry
    with the **real** total request duration after the full response is built.

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

            setattr(request, _REQUEST_ATTR, meta)

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
    """Build and emit the structured log message."""
    error = meta.get("error")
    status = "error" if error else "success"

    parts = [
        f"operation_type={meta['operation_type']}",
        f"operation_name={meta['operation_name']}",
        f"user={meta['user']}",
        f"duration_ms={duration_ms:.1f}",
        f"status={status}",
    ]

    if error:
        parts.append(f"error_type={type(error).__name__}")

    query_body = meta.get("query_body")
    if query_body:
        parts.append(f"query={query_body}")

    variables = meta.get("variables")
    if variables:
        parts.append(f"variables={variables}")

    message = " ".join(parts)
    log = _get_logger()

    if error:
        log.warning(message)
    else:
        log.info(message)


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

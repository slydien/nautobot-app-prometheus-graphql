# graphene-django-observability

<p align="center">
  <a href="https://github.com/slydien/nautobot-app-graphql-observability/actions"><img src="https://github.com/slydien/nautobot-app-graphql-observability/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <a href="https://pypi.org/project/graphene-django-observability/"><img src="https://img.shields.io/pypi/v/graphene-django-observability" alt="PyPI version"></a>
  <a href="https://pypi.org/project/graphene-django-observability/"><img src="https://img.shields.io/pypi/dm/graphene-django-observability" alt="PyPI downloads"></a>
  <br>
  Prometheus metrics and structured query logging for <a href="https://docs.graphene-python.org/projects/django/">graphene-django</a> — works with any Django project.
</p>

## Overview

`graphene-django-observability` is a generic Django library that provides comprehensive observability for any [graphene-django](https://docs.graphene-python.org/projects/django/) GraphQL API.
It ships two [Graphene middlewares](https://docs.graphene-python.org/en/latest/execution/middleware/) that instrument every GraphQL operation with Prometheus metrics and optional structured query logging — with zero changes to your application code.

### Features

**Prometheus Metrics** (`PrometheusMiddleware`):

- **Request metrics**: Count and measure the duration of all GraphQL queries and mutations.
- **Error tracking**: Count errors by operation and exception type.
- **Query depth & complexity**: Histogram metrics for nesting depth and total field count.
- **Per-user tracking**: Count requests per authenticated user for auditing and capacity planning.
- **Per-field resolution**: Optionally measure individual field resolver durations (useful for debugging).
- A built-in `/metrics/` endpoint is provided for Prometheus scraping.

**Query Logging** (`GraphQLQueryLoggingMiddleware`):

- **Structured log entries**: Operation type, name, user, duration, and status for every query.
- **Optional query body and variables**: Include the full query text and variables in log entries.
- **Standard Python logging**: Route logs to any backend (file, syslog, ELK, Loki, etc.) via Django's `LOGGING` configuration.

### Quick Install

```shell
pip install graphene-django-observability
```

```python
# settings.py
INSTALLED_APPS = [
    ...
    "graphene_django_observability",
]

MIDDLEWARE = [
    ...
    "graphene_django_observability.django_middleware.GraphQLObservabilityDjangoMiddleware",
]

GRAPHENE = {
    "SCHEMA": "myapp.schema.schema",
    "MIDDLEWARE": [
        "graphene_django_observability.middleware.PrometheusMiddleware",
        # optional structured query logging:
        "graphene_django_observability.logging_middleware.GraphQLQueryLoggingMiddleware",
    ],
}

# optional — expose a /metrics/ endpoint
# urls.py
from django.urls import include, path

urlpatterns = [
    ...
    path("graphql-observability/", include("graphene_django_observability.urls")),
]
```

## Configuration

All settings are optional. Configure via `GRAPHENE_OBSERVABILITY` in `settings.py`:

```python
GRAPHENE_OBSERVABILITY = {
    # Paths to instrument (default: ["/graphql/"])
    "graphql_paths": ["/graphql/"],
    # Prometheus metrics
    "graphql_metrics_enabled": True,
    "track_query_depth": True,
    "track_query_complexity": True,
    "track_field_resolution": False,   # enables per-field timing (high overhead)
    "track_per_user": True,
    # Query logging
    "query_logging_enabled": False,
    "log_query_body": False,
    "log_query_variables": False,      # warning: may log sensitive data
}
```

## Prometheus Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `graphql_requests_total` | Counter | `operation_type`, `operation_name`, `status` | Total requests (success / error). |
| `graphql_request_duration_seconds` | Histogram | `operation_type`, `operation_name` | Full request duration in seconds. |
| `graphql_errors_total` | Counter | `operation_type`, `operation_name`, `error_type` | Errors by exception type. |
| `graphql_query_depth` | Histogram | `operation_name` | Query nesting depth. |
| `graphql_query_complexity` | Histogram | `operation_name` | Total field count. |
| `graphql_field_resolution_duration_seconds` | Histogram | `type_name`, `field_name` | Per-field resolver duration (opt-in). |
| `graphql_requests_by_user_total` | Counter | `user`, `operation_type`, `operation_name` | Requests per authenticated user. |

## Documentation

Full documentation is available in the [`docs`](https://github.com/slydien/nautobot-app-graphql-observability/tree/main/docs) folder:

- **User Guide** (`docs/user/`) — Overview, Getting Started, Use Cases, FAQ.
- **Administrator Guide** (`docs/admin/`) — Installation, Configuration, Upgrade, Uninstall.
- **Developer Guide** (`docs/dev/`) — Extending, Code Reference, Contributing.

## Questions & Contributing

For questions, check the [FAQ](user/faq.md) or open an [issue](https://github.com/slydien/nautobot-app-graphql-observability/issues).
Contributions are very welcome — see the [contributing guide](dev/contributing.md).

# Project: graphene-django-observability

## Project Overview

`graphene-django-observability` is a **generic Django library** that adds Prometheus metrics and structured query logging to any Django project using [graphene-django](https://docs.graphene-python.org/projects/django/). It has **no dependency on Nautobot** and works with any Django + graphene-django stack.

## Package Structure

```
graphene_django_observability/
├── __init__.py              # Django AppConfig
├── middleware.py            # PrometheusMiddleware (Graphene middleware)
├── django_middleware.py     # GraphQLObservabilityDjangoMiddleware (HTTP layer timing)
├── logging_middleware.py    # GraphQLQueryLoggingMiddleware (structured query logs)
├── metrics.py               # prometheus_client metric definitions
├── utils.py                 # Query depth/complexity helpers
├── views.py                 # metrics_view (exposes /metrics/ endpoint)
├── urls.py                  # URL pattern: path("metrics/", metrics_view)
└── tests/
    ├── test_middleware.py
    ├── test_django_middleware.py
    └── test_logging_middleware.py
```

## How It Works

### Two-Layer Instrumentation

1. **Graphene middleware** (`PrometheusMiddleware`): Called for every field resolution by the Graphene engine. Detects root-resolver calls (`root is None`) and stashes operation metadata (`operation_type`, `operation_name`, `user`, `depth`, `complexity`) on the request object.

2. **Django middleware** (`GraphQLObservabilityDjangoMiddleware`): Wraps the HTTP request/response cycle. Reads metadata stashed by the Graphene middleware after the response is complete and records duration histograms. This gives accurate wall-clock timing including serialization.

3. **Logging middleware** (`GraphQLQueryLoggingMiddleware`): Graphene middleware that emits one structured log entry per operation to the `graphene_django_observability.graphql_query_log` logger.

### Settings

All configuration lives under a single Django settings key:

```python
GRAPHENE_OBSERVABILITY = {
    "graphql_metrics_enabled": True,      # Master switch
    "track_query_depth": True,             # graphql_query_depth histogram
    "track_query_complexity": True,        # graphql_query_complexity histogram
    "track_field_resolution": False,       # Per-field timing (high overhead, debugging only)
    "track_per_user": True,               # graphql_requests_by_user_total counter
    "graphql_paths": None,                # Set of URL paths to instrument (default: {"/graphql/"})
    "query_logging_enabled": False,        # Enable GraphQLQueryLoggingMiddleware
    "log_query_body": False,              # Include full query text in log
    "log_query_variables": False,         # Include query variables in log
}
```

### Installation in a Django Project

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
    ],
}

# urls.py
from django.urls import include, path

urlpatterns = [
    ...
    path("", include("graphene_django_observability.urls")),
]
```

## Prometheus Metrics Exposed

| Metric | Type | Labels |
|--------|------|--------|
| `graphql_requests_total` | Counter | `operation_type`, `operation_name`, `status` |
| `graphql_request_duration_seconds` | Histogram | `operation_type`, `operation_name` |
| `graphql_errors_total` | Counter | `operation_type`, `operation_name`, `error_type` |
| `graphql_query_depth` | Histogram | `operation_name` |
| `graphql_query_complexity` | Histogram | `operation_name` |
| `graphql_requests_by_user_total` | Counter | `user` |
| `graphql_field_resolution_duration_seconds` | Histogram | `type_name`, `field_name` |

## Development

```bash
# Install all dependencies
poetry install

# Run tests
poetry run python -m django test graphene_django_observability --settings=test_settings --verbosity=2

# Run linters
poetry run ruff format --check .
poetry run ruff check .
poetry run yamllint .

# Serve docs locally
poetry run mkdocs serve

# Build docs (strict mode, as CI does)
poetry run mkdocs build --strict
```

## CI Pipeline (`.github/workflows/ci.yml`)

| Job | Command | Install flag |
|-----|---------|-------------|
| lint-format | `ruff format --check` | `--without docs` |
| lint-ruff | `ruff check` | `--without docs` |
| yamllint | `yamllint .` | `--without docs` |
| test (3.10–3.13) | `python -m django test ... --settings=test_settings` | `poetry install` |
| test-coverage | `coverage run ...` | `poetry install` |
| docs | `mkdocs build --strict` | `poetry install` |
| changelog | `towncrier check` | `--without docs` |

## Key Architecture Decisions

See `docs/dev/arch_decision.md` for full ADRs. Summary:

- **ADR-1**: Use Graphene middleware (not Django middleware) for operation-level metrics — only Graphene middleware has access to `GraphQLResolveInfo` with operation names, types, and field data.
- **ADR-2**: Use `time.monotonic()` for duration — immune to NTP clock adjustments.
- **ADR-3**: Low-cardinality label design — field-level tracking is opt-in behind `track_field_resolution`.
- **ADR-4**: Instrument only at root resolver level (`root is None`) for basic metrics — avoids N×field_count inflated counts.

## currentDate
Today's date is 2026-02-20.

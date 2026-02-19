"""Prometheus metric definitions for GraphQL instrumentation."""

from prometheus_client import Counter, Histogram

# --- Basic metrics (Phase 1) ---

graphql_requests_total = Counter(
    "graphql_requests_total",
    "Total number of GraphQL requests",
    ["operation_type", "operation_name", "status"],
)

graphql_request_duration_seconds = Histogram(
    "graphql_request_duration_seconds",
    "Duration of GraphQL request execution in seconds",
    ["operation_type", "operation_name"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

graphql_errors_total = Counter(
    "graphql_errors_total",
    "Total number of GraphQL errors",
    ["operation_type", "operation_name", "error_type"],
)

# --- Advanced metrics (Phase 2) ---

graphql_query_depth = Histogram(
    "graphql_query_depth",
    "Depth of GraphQL queries",
    ["operation_name"],
    buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20],
)

graphql_query_complexity = Histogram(
    "graphql_query_complexity",
    "Complexity of GraphQL queries measured by total field count",
    ["operation_name"],
    buckets=[1, 5, 10, 20, 50, 100, 200, 500, 1000, 2000],
)

graphql_field_resolution_duration_seconds = Histogram(
    "graphql_field_resolution_duration_seconds",
    "Duration of individual GraphQL field resolution in seconds",
    ["type_name", "field_name"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0],
)

# --- Per-user metrics (Phase 3) ---

graphql_requests_by_user_total = Counter(
    "graphql_requests_by_user_total",
    "Total number of GraphQL requests per user",
    ["user", "operation_type", "operation_name"],
)

"""Tests for the GraphQLObservabilityDjangoMiddleware."""

from unittest.mock import MagicMock

from django.test import RequestFactory, TestCase, override_settings

from graphene_django_observability.django_middleware import (
    GraphQLObservabilityDjangoMiddleware,
    _record_observability,
)
from graphene_django_observability.logging_middleware import (
    _REQUEST_ATTR as _LOGGING_ATTR,
)
from graphene_django_observability.metrics import (
    graphql_request_duration_seconds,
)
from graphene_django_observability.middleware import (
    _REQUEST_ATTR as _PROM_ATTR,
)


class GraphQLObservabilityDjangoMiddlewareTest(TestCase):
    """Test cases for the Django HTTP middleware."""

    def setUp(self):
        self.factory = RequestFactory()
        self.get_response = MagicMock(return_value=MagicMock(status_code=200))
        self.middleware = GraphQLObservabilityDjangoMiddleware(self.get_response)

    def test_non_graphql_path_passes_through(self):
        request = self.factory.get("/api/dcim/devices/")
        response = self.middleware(request)

        self.get_response.assert_called_once_with(request)
        self.assertEqual(response.status_code, 200)

    def test_graphql_path_records_observability(self):
        request = self.factory.post("/graphql/")
        setattr(
            request,
            _PROM_ATTR,
            {"operation_type": "query", "operation_name": "DjangoMWTest"},
        )

        before = graphql_request_duration_seconds.labels(
            operation_type="query", operation_name="DjangoMWTest"
        )._sum.get()

        self.middleware(request)

        after = graphql_request_duration_seconds.labels(
            operation_type="query", operation_name="DjangoMWTest"
        )._sum.get()
        self.assertGreater(after, before)

    def test_no_stashed_metadata_is_safe(self):
        request = self.factory.post("/graphql/")
        # No metadata stashed — should not raise
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)


class RecordObservabilityTest(TestCase):
    """Test cases for _record_observability helper."""

    def test_records_prometheus_duration(self):
        request = MagicMock()
        setattr(
            request,
            _PROM_ATTR,
            {"operation_type": "query", "operation_name": "PromTest"},
        )
        delattr(request, _LOGGING_ATTR)

        before = graphql_request_duration_seconds.labels(operation_type="query", operation_name="PromTest")._sum.get()

        _record_observability(request, 0.123)

        after = graphql_request_duration_seconds.labels(operation_type="query", operation_name="PromTest")._sum.get()
        self.assertAlmostEqual(after - before, 0.123, places=3)

    def test_emits_log(self):
        request = MagicMock()
        delattr(request, _PROM_ATTR)
        meta = {
            "operation_type": "query",
            "operation_name": "LogTest",
            "user": "admin",
        }
        setattr(request, _LOGGING_ATTR, meta)

        with self.assertLogs("graphene_django_observability.graphql_query_log", level="INFO") as logs:
            _record_observability(request, 0.050)

        self.assertEqual(len(logs.output), 1)
        self.assertEqual(logs.records[0].duration_ms, 50.0)


class ConfigurableGraphQLPathsTest(TestCase):
    """Test that graphql_paths can be overridden via settings."""

    def setUp(self):
        self.factory = RequestFactory()
        self.get_response = MagicMock(return_value=MagicMock(status_code=200))

    @override_settings(GRAPHENE_OBSERVABILITY={"graphql_paths": ["/custom/graphql/"]})
    def test_custom_path_is_instrumented(self):
        middleware = GraphQLObservabilityDjangoMiddleware(self.get_response)
        request = self.factory.post("/custom/graphql/")
        setattr(
            request,
            _PROM_ATTR,
            {"operation_type": "query", "operation_name": "CustomPathTest"},
        )

        from graphene_django_observability.metrics import graphql_request_duration_seconds

        before = graphql_request_duration_seconds.labels(
            operation_type="query", operation_name="CustomPathTest"
        )._sum.get()

        middleware(request)

        after = graphql_request_duration_seconds.labels(
            operation_type="query", operation_name="CustomPathTest"
        )._sum.get()
        self.assertGreater(after, before)

    @override_settings(GRAPHENE_OBSERVABILITY={"graphql_paths": ["/custom/graphql/"]})
    def test_default_path_is_not_instrumented_with_custom_config(self):
        middleware = GraphQLObservabilityDjangoMiddleware(self.get_response)
        request = self.factory.post("/graphql/")

        # The default path is no longer in the configured set — should pass through
        middleware(request)
        self.get_response.assert_called_once_with(request)


class MetricsViewTest(TestCase):
    """Test the /metrics/ Prometheus scrape endpoint."""

    def test_metrics_view_returns_200(self):
        from django.test import RequestFactory as RF

        from graphene_django_observability.views import metrics_view

        request = RF().get("/graphql-observability/metrics/")
        response = metrics_view(request)
        self.assertEqual(response.status_code, 200)

    def test_metrics_view_content_type(self):
        from django.test import RequestFactory as RF

        from graphene_django_observability.views import metrics_view

        request = RF().get("/graphql-observability/metrics/")
        response = metrics_view(request)
        self.assertIn("text/plain", response["Content-Type"])

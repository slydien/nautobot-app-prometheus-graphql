"""Tests for the PrometheusMiddleware Graphene middleware."""

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from graphql import parse

from graphene_django_observability.metrics import (
    graphql_errors_total,
    graphql_field_resolution_duration_seconds,
    graphql_query_complexity,
    graphql_query_depth,
    graphql_requests_by_user_total,
    graphql_requests_total,
)
from graphene_django_observability.middleware import (
    _REQUEST_ATTR,
    PrometheusMiddleware,
)


def _make_info(operation_type="query", operation_name="TestQuery"):
    """Build a mock GraphQLResolveInfo with the given operation metadata."""
    info = MagicMock()
    info.operation.operation.value = operation_type
    if operation_name:
        info.operation.name.value = operation_name
    else:
        info.operation.name = None
    # Ensure hasattr(_REQUEST_ATTR) returns False initially.
    del info.context._graphql_prometheus_meta
    return info


def _make_info_with_ast(query_string, operation_name=None):
    """Build a mock GraphQLResolveInfo with a real parsed AST.

    This gives the middleware real SelectionSetNode objects so that
    depth/complexity calculations run against actual AST nodes.
    """
    doc = parse(query_string)
    op = doc.definitions[0]
    fragments = {frag.name.value: frag for frag in doc.definitions[1:]}

    info = MagicMock()
    info.operation = op
    info.fragments = fragments
    info.context.user.is_authenticated = True
    info.context.user.username = "testuser"
    # Ensure hasattr(_REQUEST_ATTR) returns False initially.
    del info.context._graphql_prometheus_meta
    if operation_name is not None:
        info.operation.name = MagicMock()
        info.operation.name.value = operation_name
    return info


# Default config enabling all advanced metrics
_DEFAULT_CONFIG = {
    "track_query_depth": True,
    "track_query_complexity": True,
    "track_per_user": True,
    "track_field_resolution": False,
}


class PrometheusMiddlewareBasicTest(TestCase):
    """Test cases for basic PrometheusMiddleware functionality."""

    def setUp(self):
        self.middleware = PrometheusMiddleware()
        self.next_func = MagicMock(return_value="resolved_value")

    @patch("graphene_django_observability.middleware._get_app_settings", return_value=_DEFAULT_CONFIG)
    def test_root_resolver_increments_request_counter(self, _mock_settings):
        info = _make_info(operation_type="query", operation_name="GetDevices")
        before = graphql_requests_total.labels(
            operation_type="query", operation_name="GetDevices", status="success"
        )._value.get()

        result = self.middleware.resolve(self.next_func, None, info)

        self.assertEqual(result, "resolved_value")
        self.next_func.assert_called_once_with(None, info)

        after = graphql_requests_total.labels(
            operation_type="query", operation_name="GetDevices", status="success"
        )._value.get()
        self.assertEqual(after - before, 1)

    @patch("graphene_django_observability.middleware._get_app_settings", return_value=_DEFAULT_CONFIG)
    def test_nested_resolver_skips_metrics(self, _mock_settings):
        info = _make_info()
        parent = {"some": "parent"}
        result = self.middleware.resolve(self.next_func, parent, info)

        self.assertEqual(result, "resolved_value")
        self.next_func.assert_called_once_with(parent, info)

    @patch("graphene_django_observability.middleware._get_app_settings", return_value=_DEFAULT_CONFIG)
    def test_unnamed_operation_uses_root_field(self, _mock_settings):
        info = _make_info_with_ast("{ devices { id } }")
        before = graphql_requests_total.labels(
            operation_type="query", operation_name="devices", status="success"
        )._value.get()

        self.middleware.resolve(self.next_func, None, info)

        after = graphql_requests_total.labels(
            operation_type="query", operation_name="devices", status="success"
        )._value.get()
        self.assertEqual(after - before, 1)

    @patch("graphene_django_observability.middleware._get_app_settings", return_value=_DEFAULT_CONFIG)
    def test_unnamed_operation_multiple_root_fields(self, _mock_settings):
        info = _make_info_with_ast("{ devices { id } locations { id } }")
        before = graphql_requests_total.labels(
            operation_type="query", operation_name="devices,locations", status="success"
        )._value.get()

        self.middleware.resolve(self.next_func, None, info)

        after = graphql_requests_total.labels(
            operation_type="query", operation_name="devices,locations", status="success"
        )._value.get()
        self.assertEqual(after - before, 1)

    @patch("graphene_django_observability.middleware._get_app_settings", return_value=_DEFAULT_CONFIG)
    def test_error_increments_error_counter(self, _mock_settings):
        info = _make_info(operation_type="mutation", operation_name="CreateDevice")
        self.next_func.side_effect = ValueError("bad input")

        error_before = graphql_errors_total.labels(
            operation_type="mutation", operation_name="CreateDevice", error_type="ValueError"
        )._value.get()
        request_before = graphql_requests_total.labels(
            operation_type="mutation", operation_name="CreateDevice", status="error"
        )._value.get()

        with self.assertRaises(ValueError):
            self.middleware.resolve(self.next_func, None, info)

        error_after = graphql_errors_total.labels(
            operation_type="mutation", operation_name="CreateDevice", error_type="ValueError"
        )._value.get()
        self.assertEqual(error_after - error_before, 1)

        request_after = graphql_requests_total.labels(
            operation_type="mutation", operation_name="CreateDevice", status="error"
        )._value.get()
        self.assertEqual(request_after - request_before, 1)

    @patch("graphene_django_observability.middleware._get_app_settings", return_value=_DEFAULT_CONFIG)
    def test_root_resolver_stashes_labels_for_duration(self, _mock_settings):
        info = _make_info(operation_type="query", operation_name="StashTest")

        self.middleware.resolve(self.next_func, None, info)

        meta = getattr(info.context, _REQUEST_ATTR)
        self.assertEqual(meta["operation_type"], "query")
        self.assertEqual(meta["operation_name"], "StashTest")


class PrometheusMiddlewareAdvancedTest(TestCase):
    """Test cases for advanced metrics: depth, complexity, per-user, per-field."""

    def setUp(self):
        self.middleware = PrometheusMiddleware()
        self.next_func = MagicMock(return_value="resolved_value")

    @patch("graphene_django_observability.middleware._get_app_settings", return_value=_DEFAULT_CONFIG)
    def test_query_depth_recorded(self, _mock_settings):
        info = _make_info_with_ast(
            "query DepthTest { devices { location { parent { name } } } }",
            operation_name="DepthTest",
        )
        before = graphql_query_depth.labels(operation_name="DepthTest")._sum.get()

        self.middleware.resolve(self.next_func, None, info)

        after = graphql_query_depth.labels(operation_name="DepthTest")._sum.get()
        # depth of devices.location.parent.name = 4
        self.assertEqual(after - before, 4)

    @patch("graphene_django_observability.middleware._get_app_settings", return_value=_DEFAULT_CONFIG)
    def test_query_complexity_recorded(self, _mock_settings):
        info = _make_info_with_ast(
            "query ComplexityTest { devices { id name location { name } } }",
            operation_name="ComplexityTest",
        )
        before = graphql_query_complexity.labels(operation_name="ComplexityTest")._sum.get()

        self.middleware.resolve(self.next_func, None, info)

        after = graphql_query_complexity.labels(operation_name="ComplexityTest")._sum.get()
        # devices + id + name + location + name = 5
        self.assertEqual(after - before, 5)

    @patch("graphene_django_observability.middleware._get_app_settings", return_value=_DEFAULT_CONFIG)
    def test_per_user_metric_authenticated(self, _mock_settings):
        info = _make_info_with_ast("query UserTest { devices { id } }", operation_name="UserTest")
        info.context.user.is_authenticated = True
        info.context.user.username = "admin"

        before = graphql_requests_by_user_total.labels(
            user="admin", operation_type="query", operation_name="UserTest"
        )._value.get()

        self.middleware.resolve(self.next_func, None, info)

        after = graphql_requests_by_user_total.labels(
            user="admin", operation_type="query", operation_name="UserTest"
        )._value.get()
        self.assertEqual(after - before, 1)

    @patch("graphene_django_observability.middleware._get_app_settings", return_value=_DEFAULT_CONFIG)
    def test_per_user_metric_anonymous(self, _mock_settings):
        info = _make_info_with_ast("query AnonTest { devices { id } }", operation_name="AnonTest")
        info.context.user.is_authenticated = False

        before = graphql_requests_by_user_total.labels(
            user="anonymous", operation_type="query", operation_name="AnonTest"
        )._value.get()

        self.middleware.resolve(self.next_func, None, info)

        after = graphql_requests_by_user_total.labels(
            user="anonymous", operation_type="query", operation_name="AnonTest"
        )._value.get()
        self.assertEqual(after - before, 1)

    @patch(
        "graphene_django_observability.middleware._get_app_settings",
        return_value={"track_query_depth": False, "track_query_complexity": False, "track_per_user": False},
    )
    def test_advanced_metrics_disabled(self, _mock_settings):
        info = _make_info_with_ast("query DisabledTest { devices { id } }", operation_name="DisabledTest")

        depth_before = graphql_query_depth.labels(operation_name="DisabledTest")._sum.get()
        complexity_before = graphql_query_complexity.labels(operation_name="DisabledTest")._sum.get()
        user_before = graphql_requests_by_user_total.labels(
            user="testuser", operation_type="query", operation_name="DisabledTest"
        )._value.get()

        self.middleware.resolve(self.next_func, None, info)

        self.assertEqual(graphql_query_depth.labels(operation_name="DisabledTest")._sum.get(), depth_before)
        self.assertEqual(graphql_query_complexity.labels(operation_name="DisabledTest")._sum.get(), complexity_before)
        self.assertEqual(
            graphql_requests_by_user_total.labels(
                user="testuser", operation_type="query", operation_name="DisabledTest"
            )._value.get(),
            user_before,
        )

    @patch(
        "graphene_django_observability.middleware._get_app_settings",
        return_value={"track_field_resolution": True},
    )
    def test_field_resolution_tracking(self, _mock_settings):
        info = MagicMock()
        info.parent_type.name = "DeviceType"
        info.field_name = "name"

        parent = {"some": "parent"}
        before = graphql_field_resolution_duration_seconds.labels(type_name="DeviceType", field_name="name")._sum.get()

        self.middleware.resolve(self.next_func, parent, info)

        after = graphql_field_resolution_duration_seconds.labels(type_name="DeviceType", field_name="name")._sum.get()
        self.assertGreater(after, before)

    @patch(
        "graphene_django_observability.middleware._get_app_settings",
        return_value={"track_field_resolution": False},
    )
    def test_field_resolution_disabled(self, _mock_settings):
        info = MagicMock()
        info.parent_type.name = "DeviceType"
        info.field_name = "disabled_field"

        parent = {"some": "parent"}
        before = graphql_field_resolution_duration_seconds.labels(
            type_name="DeviceType", field_name="disabled_field"
        )._sum.get()

        self.middleware.resolve(self.next_func, parent, info)

        after = graphql_field_resolution_duration_seconds.labels(
            type_name="DeviceType", field_name="disabled_field"
        )._sum.get()
        self.assertEqual(after, before)


class GetAppSettingsTest(TestCase):
    """Test cases for _get_app_settings() settings resolution."""

    def test_returns_defaults_when_no_settings_configured(self):
        from graphene_django_observability.middleware import _get_app_settings

        config = _get_app_settings()
        self.assertTrue(config["graphql_metrics_enabled"])
        self.assertTrue(config["track_query_depth"])
        self.assertTrue(config["track_query_complexity"])
        self.assertFalse(config["track_field_resolution"])
        self.assertTrue(config["track_per_user"])
        self.assertFalse(config["query_logging_enabled"])

    @override_settings(GRAPHENE_OBSERVABILITY={"track_query_depth": False, "track_per_user": False})
    def test_graphene_observability_setting_overrides_defaults(self):
        from graphene_django_observability.middleware import _get_app_settings

        config = _get_app_settings()
        # Overridden values
        self.assertFalse(config["track_query_depth"])
        self.assertFalse(config["track_per_user"])
        # Defaults for keys not overridden
        self.assertTrue(config["graphql_metrics_enabled"])
        self.assertTrue(config["track_query_complexity"])

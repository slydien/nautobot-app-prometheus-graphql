"""Tests for the GraphQLQueryLoggingMiddleware and _emit_log."""
# pylint: disable=duplicate-code

from unittest.mock import MagicMock, patch

from django.test import TestCase
from graphql import parse

from nautobot_app_graphql_observability.logging_middleware import (
    _REQUEST_ATTR,
    GraphQLQueryLoggingMiddleware,
    _emit_log,
)

LOGGER_NAME = "nautobot_app_graphql_observability.graphql_query_log"

_LOGGING_ENABLED = {
    "query_logging_enabled": True,
    "log_query_body": False,
    "log_query_variables": False,
}


def _make_info(query_string="{ devices { id } }", authenticated=True, username="testuser", variables=None):
    """Build a mock GraphQLResolveInfo with a real parsed AST."""
    doc = parse(query_string)
    op = doc.definitions[0]
    fragments = {frag.name.value: frag for frag in doc.definitions[1:]}

    info = MagicMock()
    info.operation = op
    info.fragments = fragments
    info.variable_values = variables or {}
    info.context.user.is_authenticated = authenticated
    info.context.user.username = username
    # Ensure hasattr(_REQUEST_ATTR) returns False initially.
    del info.context._graphql_logging_meta
    return info


class GraphQLQueryLoggingMiddlewareTest(TestCase):
    """Test cases for the Graphene middleware (metadata stashing)."""

    def setUp(self):
        self.middleware = GraphQLQueryLoggingMiddleware()
        self.next_func = MagicMock(return_value="resolved_value")

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value=_LOGGING_ENABLED,
    )
    def test_root_resolver_stashes_metadata(self, _mock_settings):
        info = _make_info("query GetDevices { devices { id } }")

        result = self.middleware.resolve(self.next_func, None, info)

        self.assertEqual(result, "resolved_value")
        meta = getattr(info.context, _REQUEST_ATTR)
        self.assertEqual(meta["operation_type"], "query")
        self.assertEqual(meta["operation_name"], "GetDevices")
        self.assertEqual(meta["user"], "testuser")

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value=_LOGGING_ENABLED,
    )
    def test_nested_resolver_skips_stashing(self, _mock_settings):
        info = _make_info()
        parent = {"some": "parent"}

        result = self.middleware.resolve(self.next_func, parent, info)

        self.assertEqual(result, "resolved_value")
        self.assertFalse(hasattr(info.context, _REQUEST_ATTR))

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value=_LOGGING_ENABLED,
    )
    def test_error_records_error_in_metadata(self, _mock_settings):
        info = _make_info("query FailQuery { devices { id } }")
        self.next_func.side_effect = ValueError("bad input")

        with self.assertRaises(ValueError):
            self.middleware.resolve(self.next_func, None, info)

        meta = getattr(info.context, _REQUEST_ATTR)
        self.assertIsInstance(meta["error"], ValueError)

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value={"query_logging_enabled": False},
    )
    def test_logging_disabled_skips_stashing(self, _mock_settings):
        info = _make_info()

        result = self.middleware.resolve(self.next_func, None, info)

        self.assertEqual(result, "resolved_value")
        self.assertFalse(hasattr(info.context, _REQUEST_ATTR))

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value={**_LOGGING_ENABLED, "log_query_body": True},
    )
    def test_stashes_query_body_when_enabled(self, _mock_settings):
        info = _make_info("{ devices { id name } }")

        self.middleware.resolve(self.next_func, None, info)

        meta = getattr(info.context, _REQUEST_ATTR)
        self.assertIn("{ devices { id name } }", meta["query_body"])

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value=_LOGGING_ENABLED,
    )
    def test_no_query_body_when_disabled(self, _mock_settings):
        info = _make_info("{ devices { id name } }")

        self.middleware.resolve(self.next_func, None, info)

        meta = getattr(info.context, _REQUEST_ATTR)
        self.assertNotIn("query_body", meta)

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value={**_LOGGING_ENABLED, "log_query_variables": True},
    )
    def test_stashes_variables_when_enabled(self, _mock_settings):
        info = _make_info("{ devices { id } }", variables={"name": "test"})

        self.middleware.resolve(self.next_func, None, info)

        meta = getattr(info.context, _REQUEST_ATTR)
        self.assertEqual(meta["variables"], '{"name":"test"}')

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value=_LOGGING_ENABLED,
    )
    def test_anonymous_user(self, _mock_settings):
        info = _make_info(authenticated=False)

        self.middleware.resolve(self.next_func, None, info)

        meta = getattr(info.context, _REQUEST_ATTR)
        self.assertEqual(meta["user"], "anonymous")

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value=_LOGGING_ENABLED,
    )
    def test_unnamed_operation_uses_root_fields(self, _mock_settings):
        info = _make_info("{ devices { id } locations { id } }")

        self.middleware.resolve(self.next_func, None, info)

        meta = getattr(info.context, _REQUEST_ATTR)
        self.assertEqual(meta["operation_name"], "devices,locations")


class EmitLogTest(TestCase):
    """Test cases for _emit_log (called by the patched post() with real duration)."""

    def test_emits_log_with_duration(self):
        meta = {
            "operation_type": "query",
            "operation_name": "TestOp",
            "user": "testuser",
        }

        with self.assertLogs(LOGGER_NAME, level="INFO") as logs:
            _emit_log(meta, duration_ms=42.5)

        self.assertEqual(len(logs.output), 1)
        log_line = logs.output[0]
        self.assertIn("operation_type=query", log_line)
        self.assertIn("operation_name=TestOp", log_line)
        self.assertIn("user=testuser", log_line)
        self.assertIn("duration_ms=42.5", log_line)
        self.assertIn("status=success", log_line)

    def test_error_logs_at_warning(self):
        meta = {
            "operation_type": "query",
            "operation_name": "FailOp",
            "user": "admin",
            "error": ValueError("bad"),
        }

        with self.assertLogs(LOGGER_NAME, level="WARNING") as logs:
            _emit_log(meta, duration_ms=10.0)

        log_line = logs.output[0]
        self.assertIn("status=error", log_line)
        self.assertIn("error_type=ValueError", log_line)

    def test_query_body_in_log(self):
        meta = {
            "operation_type": "query",
            "operation_name": "BodyOp",
            "user": "admin",
            "query_body": "{ devices { id } }",
        }

        with self.assertLogs(LOGGER_NAME, level="INFO") as logs:
            _emit_log(meta, duration_ms=5.0)

        self.assertIn("query={ devices { id } }", logs.output[0])

    def test_variables_in_log(self):
        meta = {
            "operation_type": "query",
            "operation_name": "VarOp",
            "user": "admin",
            "variables": '{"name":"test"}',
        }

        with self.assertLogs(LOGGER_NAME, level="INFO") as logs:
            _emit_log(meta, duration_ms=5.0)

        self.assertIn('variables={"name":"test"}', logs.output[0])

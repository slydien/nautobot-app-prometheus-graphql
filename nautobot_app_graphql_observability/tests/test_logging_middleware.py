"""Tests for the GraphQLQueryLoggingMiddleware."""
# pylint: disable=duplicate-code

from unittest.mock import MagicMock, patch

from django.test import TestCase
from graphql import parse

from nautobot_app_graphql_observability.logging_middleware import GraphQLQueryLoggingMiddleware

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
    return info


class GraphQLQueryLoggingMiddlewareTest(TestCase):
    """Test cases for GraphQLQueryLoggingMiddleware."""

    def setUp(self):
        self.middleware = GraphQLQueryLoggingMiddleware()
        self.next_func = MagicMock(return_value="resolved_value")

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value=_LOGGING_ENABLED,
    )
    def test_root_resolver_logs_query(self, _mock_settings):
        info = _make_info("query GetDevices { devices { id } }")

        with self.assertLogs(LOGGER_NAME, level="INFO") as logs:
            result = self.middleware.resolve(self.next_func, None, info)

        self.assertEqual(result, "resolved_value")
        self.assertEqual(len(logs.output), 1)
        log_line = logs.output[0]
        self.assertIn("operation_type=query", log_line)
        self.assertIn("operation_name=GetDevices", log_line)
        self.assertIn("user=testuser", log_line)
        self.assertIn("status=success", log_line)
        self.assertIn("duration_ms=", log_line)

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value=_LOGGING_ENABLED,
    )
    def test_nested_resolver_skips_logging(self, _mock_settings):
        info = _make_info()
        parent = {"some": "parent"}

        result = self.middleware.resolve(self.next_func, parent, info)

        self.assertEqual(result, "resolved_value")
        # No assertLogs — verify no log is emitted by checking logger is not called
        with self.assertRaises(AssertionError):
            with self.assertLogs(LOGGER_NAME, level="INFO"):
                self.middleware.resolve(self.next_func, parent, info)

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value=_LOGGING_ENABLED,
    )
    def test_error_logs_at_warning(self, _mock_settings):
        info = _make_info("query FailQuery { devices { id } }")
        self.next_func.side_effect = ValueError("bad input")

        with self.assertLogs(LOGGER_NAME, level="WARNING") as logs:
            with self.assertRaises(ValueError):
                self.middleware.resolve(self.next_func, None, info)

        self.assertEqual(len(logs.output), 1)
        log_line = logs.output[0]
        self.assertIn("status=error", log_line)
        self.assertIn("error_type=ValueError", log_line)
        self.assertIn("WARNING", log_line)

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value={"query_logging_enabled": False},
    )
    def test_logging_disabled(self, _mock_settings):
        info = _make_info()

        result = self.middleware.resolve(self.next_func, None, info)

        self.assertEqual(result, "resolved_value")
        with self.assertRaises(AssertionError):
            with self.assertLogs(LOGGER_NAME, level="INFO"):
                self.middleware.resolve(self.next_func, None, info)

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value={**_LOGGING_ENABLED, "log_query_body": True},
    )
    def test_log_query_body_enabled(self, _mock_settings):
        info = _make_info("{ devices { id name } }")

        with self.assertLogs(LOGGER_NAME, level="INFO") as logs:
            self.middleware.resolve(self.next_func, None, info)

        log_line = logs.output[0]
        self.assertIn("query={ devices { id name } }", log_line)

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value=_LOGGING_ENABLED,
    )
    def test_log_query_body_disabled(self, _mock_settings):
        info = _make_info("{ devices { id name } }")

        with self.assertLogs(LOGGER_NAME, level="INFO") as logs:
            self.middleware.resolve(self.next_func, None, info)

        log_line = logs.output[0]
        self.assertNotIn("query=", log_line)

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value={**_LOGGING_ENABLED, "log_query_variables": True},
    )
    def test_log_variables_enabled(self, _mock_settings):
        info = _make_info("{ devices { id } }", variables={"name": "test"})

        with self.assertLogs(LOGGER_NAME, level="INFO") as logs:
            self.middleware.resolve(self.next_func, None, info)

        log_line = logs.output[0]
        self.assertIn('variables={"name":"test"}', log_line)

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value=_LOGGING_ENABLED,
    )
    def test_anonymous_user(self, _mock_settings):
        info = _make_info(authenticated=False)

        with self.assertLogs(LOGGER_NAME, level="INFO") as logs:
            self.middleware.resolve(self.next_func, None, info)

        log_line = logs.output[0]
        self.assertIn("user=anonymous", log_line)

    @patch(
        "nautobot_app_graphql_observability.logging_middleware._get_app_settings",
        return_value=_LOGGING_ENABLED,
    )
    def test_unnamed_operation_uses_root_fields(self, _mock_settings):
        info = _make_info("{ devices { id } locations { id } }")

        with self.assertLogs(LOGGER_NAME, level="INFO") as logs:
            self.middleware.resolve(self.next_func, None, info)

        log_line = logs.output[0]
        self.assertIn("operation_name=devices,locations", log_line)

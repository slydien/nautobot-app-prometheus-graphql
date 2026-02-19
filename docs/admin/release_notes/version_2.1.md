# v2.1 Release Notes

This document describes all new features and changes in the release. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Release Overview

- Structured JSON logging via Nautobot's built-in `setup_structlog_logging()`: all loggers now emit JSON in production with each query log field (`operation_type`, `operation_name`, `user`, `duration_ms`, `status`, etc.) as a top-level key instead of a packed string.

<!-- towncrier release notes start -->


## [v2.1.0 (2026-02-19)](https://github.com/slydien/nautobot-app-graphql-observability/releases/tag/v2.1.0)

### Added

- Added structlog JSON logging support: `setup_structlog_logging()` integration in `nautobot_config.py` routes all loggers (`django`, `nautobot`, `django.request`, and `nautobot_graphql_observability.graphql_query_log`) through a single structlog handler. With `plain_format=False` (production default), all log output is emitted as structured JSON. The query log middleware now emits operation metadata as discrete `extra` fields (`operation_type`, `operation_name`, `user`, `duration_ms`, `status`, etc.) rather than a flat key=value string, so each field appears as a top-level JSON key in log aggregators. `structlog.stdlib.ExtraAdder()` is appended to the formatter's `foreign_pre_chain` to promote these fields automatically.

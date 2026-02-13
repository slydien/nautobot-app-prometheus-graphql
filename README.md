# Nautobot App Prometheus Graphql

<p align="center">
  <a href="https://github.com/slydien/nautobot-app-prometheus-graphql/actions"><img src="https://github.com/slydien/nautobot-app-prometheus-graphql/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <a href="https://pypi.org/project/nautobot-app-prometheus-graphql/"><img src="https://img.shields.io/pypi/v/nautobot-app-prometheus-graphql"></a>
  <a href="https://pypi.org/project/nautobot-app-prometheus-graphql/"><img src="https://img.shields.io/pypi/dm/nautobot-app-prometheus-graphql"></a>
  <br>
  A Prometheus metrics app for <a href="https://nautobot.com/">Nautobot</a>.
</p>

## Overview

A Nautobot app that instruments GraphQL API queries with [Prometheus](https://prometheus.io/) metrics. It operates as a [Graphene middleware](https://docs.graphene-python.org/en/latest/execution/middleware/), intercepting GraphQL field resolutions to collect performance, usage, and error data — without modifying Nautobot's core code.

### Features

- **Request metrics**: Count and measure the duration of all GraphQL queries and mutations.
- **Error tracking**: Count errors by operation and exception type.
- **Query depth & complexity**: Histogram metrics for query nesting depth and total field count.
- **Per-user tracking**: Count requests per authenticated user for auditing and capacity planning.
- **Per-field resolution**: Optionally measure individual field resolver durations for debugging.
- **Prometheus metrics**: All metrics appear at Nautobot's default `/metrics/` endpoint — no extra endpoint needed.
- **Zero configuration**: Automatically patches Nautobot's `GraphQLDRFAPIView` to load the middleware — no manual `GRAPHENE["MIDDLEWARE"]` setup needed.

### Quick Install

```shell
pip install nautobot-app-prometheus-graphql
```

```python
# nautobot_config.py
PLUGINS = ["nautobot_app_prometheus_graphql"]
```

## Documentation

Full documentation for this App can be found over on the [Nautobot Docs](https://docs.nautobot.com) website:

- [User Guide](https://docs.nautobot.com/projects/nautobot-app-prometheus-graphql/en/latest/user/app_overview/) - Overview, Using the App, Getting Started.
- [Administrator Guide](https://docs.nautobot.com/projects/nautobot-app-prometheus-graphql/en/latest/admin/install/) - How to Install, Configure, Upgrade, or Uninstall the App.
- [Developer Guide](https://docs.nautobot.com/projects/nautobot-app-prometheus-graphql/en/latest/dev/contributing/) - Extending the App, Code Reference, Contribution Guide.
- [Release Notes / Changelog](https://docs.nautobot.com/projects/nautobot-app-prometheus-graphql/en/latest/admin/release_notes/).
- [Frequently Asked Questions](https://docs.nautobot.com/projects/nautobot-app-prometheus-graphql/en/latest/user/faq/).

### Contributing to the Documentation

You can find all the Markdown source for the App documentation under the [`docs`](https://github.com/slydien/nautobot-app-prometheus-graphql/tree/develop/docs) folder in this repository. For simple edits, a Markdown capable editor is sufficient: clone the repository and edit away.

If you need to view the fully-generated documentation site, you can build it with [MkDocs](https://www.mkdocs.org/). A container hosting the documentation can be started using the `invoke` commands (details in the [Development Environment Guide](https://docs.nautobot.com/projects/nautobot-app-prometheus-graphql/en/latest/dev/dev_environment/#docker-development-environment)) on [http://localhost:8001](http://localhost:8001). Using this container, as your changes to the documentation are saved, they will be automatically rebuilt and any pages currently being viewed will be reloaded in your browser.

Any PRs with fixes or improvements are very welcome!

## Questions

For any questions or comments, please check the [FAQ](https://docs.nautobot.com/projects/nautobot-app-prometheus-graphql/en/latest/user/faq/) first. Feel free to also swing by the [Network to Code Slack](https://networktocode.slack.com/) (channel `#nautobot`), sign up [here](http://slack.networktocode.com/) if you don't have an account.

"""Django urlpatterns for nautobot_graphql_observability.

When Nautobot is installed the URL configuration exposes the plugin docs
page (using Nautobot's static-file redirect and ``NautobotUIViewSetRouter``).

In plain Django projects a ``/metrics/`` endpoint is provided so that
Prometheus can scrape the GraphQL observability metrics.  Mount the patterns
in your root URL conf::

    from django.urls import include, path

    urlpatterns = [
        ...
        path("graphql-observability/", include("nautobot_graphql_observability.urls")),
    ]

Metrics are then available at ``/graphql-observability/metrics/``.
"""

from django.urls import path

app_name = "nautobot_graphql_observability"

try:
    from django.templatetags.static import static
    from django.views.generic import RedirectView
    from nautobot.apps.urls import NautobotUIViewSetRouter

    router = NautobotUIViewSetRouter()

    urlpatterns = [
        path(
            "docs/",
            RedirectView.as_view(url=static("nautobot_graphql_observability/docs/index.html")),
            name="docs",
        ),
    ]

    urlpatterns += router.urls

except ImportError:
    # Nautobot is not available — expose a /metrics/ endpoint instead.
    from nautobot_graphql_observability.views import metrics_view  # pylint: disable=import-outside-toplevel

    urlpatterns = [
        path("metrics/", metrics_view, name="metrics"),
    ]

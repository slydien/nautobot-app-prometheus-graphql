"""Views for the nautobot_graphql_observability app."""

from django.http import HttpResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


def metrics_view(request):
    """Expose Prometheus metrics in the standard text exposition format.

    In Nautobot deployments, metrics are served at the platform-level
    ``/metrics/`` endpoint provided by ``django-prometheus``, so this
    view is **not** wired up by the Nautobot URL configuration.

    In plain Django projects, include this view in your root URL conf::

        from django.urls import include, path

        urlpatterns = [
            ...
            path("graphql-observability/", include("nautobot_graphql_observability.urls")),
        ]

    The metrics will then be available at
    ``/graphql-observability/metrics/``.

    Returns:
        HttpResponse: Prometheus metrics in text format.
    """
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)

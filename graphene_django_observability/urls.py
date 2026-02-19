"""Django urlpatterns for graphene_django_observability.

Mount the patterns in your root URL conf to expose a Prometheus-compatible
``/metrics/`` scrape endpoint::

    from django.urls import include, path

    urlpatterns = [
        ...
        path("graphql-observability/", include("graphene_django_observability.urls")),
    ]

Metrics are then available at ``/graphql-observability/metrics/``.
"""

from django.urls import path

from graphene_django_observability.views import metrics_view

app_name = "graphene_django_observability"

urlpatterns = [
    path("metrics/", metrics_view, name="metrics"),
]

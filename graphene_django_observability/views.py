"""Views for graphene_django_observability."""

from django.http import HttpRequest, HttpResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


def metrics_view(request: HttpRequest) -> HttpResponse:
    """Expose Prometheus metrics in the standard text exposition format.

    Returns:
        HttpResponse: Prometheus metrics in text format.
    """
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)

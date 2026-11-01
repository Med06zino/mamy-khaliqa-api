from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PaymentViewSet, SasPayWebhookView, WaveWebhookView

router = DefaultRouter()
router.register("", PaymentViewSet, basename="payment")

urlpatterns = [
    path("wave/webhook/", WaveWebhookView.as_view(), name="wave-webhook"),
    path("saspay/webhook/", SasPayWebhookView.as_view(), name="saspay-webhook"),
    path("", include(router.urls)),
]

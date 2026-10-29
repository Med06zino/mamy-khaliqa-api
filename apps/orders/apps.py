from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.orders"

    def ready(self):
        import apps.orders.signals  # noqa: F401 — active les signaux
        import apps.orders.models  # noqa: F401 — pour les signaux de facture

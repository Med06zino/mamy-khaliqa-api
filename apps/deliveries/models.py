from django.db import models


class DeliveryZone(models.Model):
    name     = models.CharField("Zone", max_length=120, unique=True)
    fee      = models.PositiveIntegerField("Frais de livraison (FCFA)")
    is_active = models.BooleanField(default=True)
    info     = models.CharField("Informations complementaires", max_length=255, blank=True)
    position = models.PositiveIntegerField(default=0)
    # Délai de livraison estimé en jours ouvrés.
    # Dakar : 1–2 j ; régions proches : 2–3 j ; régions éloignées : 3–5 j.
    delivery_days_min = models.PositiveSmallIntegerField(
        "Délai minimum (jours ouvrés)", default=1
    )
    delivery_days_max = models.PositiveSmallIntegerField(
        "Délai maximum (jours ouvrés)", default=2
    )

    class Meta:
        ordering = ["position", "name"]

    def __str__(self):
        return f"{self.name} ({self.fee} FCFA)"

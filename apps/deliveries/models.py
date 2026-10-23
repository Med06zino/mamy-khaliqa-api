from django.db import models


class DeliveryZone(models.Model):
    name = models.CharField("Zone", max_length=120, unique=True)
    fee = models.PositiveIntegerField("Frais de livraison (FCFA)")
    is_active = models.BooleanField(default=True)
    info = models.CharField("Informations complementaires", max_length=255, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]

    def __str__(self):
        return f"{self.name} ({self.fee} FCFA)"

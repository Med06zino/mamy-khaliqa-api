from django.conf import settings
from django.db import models

from apps.common.validators import validate_image


class StoreSettings(models.Model):
    """Parametres uniques de la boutique (une seule ligne, pk=1)."""

    name = models.CharField("Nom de la boutique", max_length=120, default="Mamy Khaliqa")
    tagline = models.CharField(
        "Slogan", max_length=200, default="Révélez votre beauté, sublimez votre quotidien."
    )
    logo = models.ImageField(upload_to="store/", blank=True, validators=[validate_image])
    contact_email = models.EmailField("E-mail de contact", blank=True)
    contact_phone = models.CharField("Telephone", max_length=30, blank=True)
    address = models.CharField("Adresse", max_length=255, blank=True)
    whatsapp_number = models.CharField(
        "Numero WhatsApp (format international sans +)", max_length=20, blank=True
    )
    instagram_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    tiktok_url = models.URLField(blank=True)
    announcement_text = models.CharField("Bandeau d'annonce", max_length=200, blank=True)
    announcement_active = models.BooleanField(default=False)
    footer_text = models.TextField("Texte du footer", blank=True)
    low_stock_threshold = models.PositiveIntegerField("Seuil de stock faible", default=5)
    guest_checkout_enabled = models.BooleanField("Commande sans compte", default=True)
    payment_cash_on_delivery = models.BooleanField("Paiement a la livraison", default=False)
    payment_wave_enabled = models.BooleanField(
        "Paiement Wave (mobile money)",
        default=False,
        help_text="Affiche Wave comme option de règlement. Ne confirme pas automatiquement le paiement.",
    )
    payment_orange_money_enabled = models.BooleanField(
        "Paiement Orange Money (mobile money)",
        default=False,
        help_text="Affiche Orange Money comme option de règlement. Ne confirme pas automatiquement le paiement.",
    )
    unknown_zone_policy = models.TextField(
        "Procedure si la zone n'est pas configuree",
        default="Les frais de livraison seront confirmes avec vous par la boutique avant l'expedition.",
    )
    store_pickup_enabled = models.BooleanField(
        "Retrait en boutique",
        default=False,
        help_text="Permet aux clients de choisir le retrait en boutique (aucuns frais de livraison).",
    )

    class Meta:
        verbose_name = "Parametres de la boutique"
        verbose_name_plural = "Parametres de la boutique"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # singleton
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1, defaults={"whatsapp_number": settings.DEFAULT_WHATSAPP_NUMBER}
        )
        return obj

    def __str__(self):
        return self.name

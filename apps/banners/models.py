from django.db import models

from apps.common.validators import validate_image


class Banner(models.Model):
    """Bannière affichée sur la page d'accueil.

    Deux types :
    - hero   : bandeau principal en haut de page (une seule active recommandée)
    - promo  : carrousel promotionnel (plusieurs possibles, triées par position)

    Règle métier :
    - L'administrateur crée, modifie et active/désactive les bannières.
    - Seules les bannières actives (is_active=True) sont exposées publiquement.
    - Le titre et l'image sont obligatoires. Sous-titre, texte bouton et lien sont optionnels.
    - Si link_url est vide, le bouton pointe vers /boutique par convention frontend.
    """

    class BannerType(models.TextChoices):
        HERO  = "hero",  "Hero principal"
        PROMO = "promo", "Promotionnel"

    banner_type  = models.CharField("Type", max_length=10, choices=BannerType.choices, default=BannerType.HERO, db_index=True)
    title        = models.CharField("Titre", max_length=200)
    subtitle     = models.CharField("Sous-titre", max_length=300, blank=True)
    image        = models.ImageField("Image", upload_to="banners/", validators=[validate_image])
    button_text  = models.CharField("Texte du bouton", max_length=80, blank=True, default="Découvrir la boutique")
    link_url     = models.CharField("URL du lien (chemin relatif ou absolu)", max_length=255, blank=True)
    position     = models.PositiveIntegerField("Ordre d'affichage", default=0)
    is_active    = models.BooleanField("Active", default=True, db_index=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]
        verbose_name = "Bannière"
        verbose_name_plural = "Bannières"

    def __str__(self):
        return f"[{self.get_banner_type_display()}] {self.title}"

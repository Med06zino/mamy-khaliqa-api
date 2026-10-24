from django.db import models


class NewsletterSubscriber(models.Model):
    """Abonné à la newsletter.

    Règle métier :
    - Un e-mail ne peut être abonné qu'une seule fois (unicité).
    - Un abonné peut être désactivé (is_active=False) par l'admin sans suppression.
    - La date d'abonnement est tracée pour les exports.
    - L'abonnement est volontaire : le frontend doit recueillir un consentement explicite.
    """

    email         = models.EmailField("E-mail", unique=True)
    is_active     = models.BooleanField("Actif", default=True)
    subscribed_at = models.DateTimeField("Date d'abonnement", auto_now_add=True)

    class Meta:
        ordering = ["-subscribed_at"]
        verbose_name = "Abonné newsletter"
        verbose_name_plural = "Abonnés newsletter"

    def __str__(self):
        return self.email

from django.db import models
from django.db.models import Q
from django.utils.text import slugify

from apps.common.validators import validate_image


def unique_slug(model, value, instance=None):
    base = slugify(value) or "item"
    slug, n = base, 2
    qs = model.objects.all()
    if instance and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    while qs.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="categories/", blank=True, validators=[validate_image])
    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Category, self.name, self)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def public(self):
        return self.filter(is_published=True, is_archived=False, category__is_active=True)


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    sku = models.CharField("Reference SKU", max_length=60, unique=True)
    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    price = models.PositiveIntegerField("Prix (FCFA)")
    compare_at_price = models.PositiveIntegerField(
        "Ancien prix (FCFA), uniquement si promotion reelle", null=True, blank=True
    )
    stock = models.PositiveIntegerField(
        "Stock (utilise si le produit n'a pas de variantes)", default=0
    )
    volume = models.CharField("Contenance / format", max_length=60, blank=True)
    ingredients = models.TextField("Composition (fournie par la marque)", blank=True)
    usage_tips = models.TextField("Conseils d'utilisation valides", blank=True)
    precautions = models.TextField("Precautions", blank=True)
    is_published = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_published", "is_archived", "-created_at"]),
            models.Index(fields=["price"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(compare_at_price__isnull=True) | Q(compare_at_price__gt=models.F("price")),
                name="promo_price_greater_than_price",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Product, self.name, self)
        super().save(*args, **kwargs)

    @property
    def has_variants(self):
        return self.variants.filter(is_active=True).exists()

    @property
    def available_stock(self):
        if self.has_variants:
            return sum(v.stock for v in self.variants.filter(is_active=True))
        return self.stock

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/", validators=[validate_image])
    alt = models.CharField(max_length=200, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=120)
    sku = models.CharField(max_length=60, unique=True)
    price = models.PositiveIntegerField("Prix specifique (FCFA), optionnel", null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]

    @property
    def effective_price(self):
        return self.price if self.price is not None else self.product.price

    def __str__(self):
        return f"{self.product.name} - {self.name}"


class StockMovement(models.Model):
    class Reason(models.TextChoices):
        ORDER = "order", "Commande"
        CANCEL = "cancel", "Annulation"
        ADJUST = "adjust", "Ajustement manuel"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_movements")
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.SET_NULL)
    delta = models.IntegerField()
    reason = models.CharField(max_length=10, choices=Reason.choices)
    reference = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

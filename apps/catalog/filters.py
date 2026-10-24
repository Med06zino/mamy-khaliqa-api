import django_filters as df

from .models import Product


class ProductFilter(df.FilterSet):
    category  = df.CharFilter(field_name="category__slug")
    min_price = df.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = df.NumberFilter(field_name="price", lookup_expr="lte")
    in_stock  = df.BooleanFilter(method="filter_in_stock")
    has_promo = df.BooleanFilter(method="filter_has_promo")

    class Meta:
        model = Product
        fields = ["category", "min_price", "max_price", "in_stock", "has_promo"]

    def filter_in_stock(self, qs, name, value):
        if value is True:
            return qs.filter(avail__gt=0)
        if value is False:
            return qs.filter(avail__lte=0)
        return qs

    def filter_has_promo(self, qs, name, value):
        """Filtre les produits avec un ancien prix (vraie promotion)."""
        if value is True:
            return qs.filter(compare_at_price__isnull=False)
        if value is False:
            return qs.filter(compare_at_price__isnull=True)
        return qs

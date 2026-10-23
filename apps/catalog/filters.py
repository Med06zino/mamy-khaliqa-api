import django_filters as df

from .models import Product


class ProductFilter(df.FilterSet):
    category = df.CharFilter(field_name="category__slug")
    min_price = df.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = df.NumberFilter(field_name="price", lookup_expr="lte")
    in_stock = df.BooleanFilter(method="filter_in_stock")

    class Meta:
        model = Product
        fields = ["category", "min_price", "max_price", "in_stock"]

    def filter_in_stock(self, qs, name, value):
        if value is True:
            return qs.filter(avail__gt=0)
        if value is False:
            return qs.filter(avail__lte=0)
        return qs

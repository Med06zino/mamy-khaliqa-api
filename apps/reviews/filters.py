import django_filters as df

from .models import Review


class ReviewFilter(df.FilterSet):
    product = df.CharFilter(field_name="product__slug")

    class Meta:
        model = Review
        fields = ["product"]

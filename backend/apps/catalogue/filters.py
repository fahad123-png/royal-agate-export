import django_filters
from django import forms

from .models import Product


class ProductFilterForm(forms.Form):

    def clean(self):
        cleaned_data = super().clean()

        min_price = cleaned_data.get("min_price")
        max_price = cleaned_data.get("max_price")

        if (
            min_price is not None
            and max_price is not None
            and min_price > max_price
        ):
            self.add_error(
                "min_price",
                "Minimum price cannot be greater than maximum price."
            )

        return cleaned_data


class ProductFilter(django_filters.FilterSet):

    min_price = django_filters.NumberFilter(
        field_name="retail_price",
        lookup_expr="gte",
        min_value=0
    )

    max_price = django_filters.NumberFilter(
        field_name="retail_price",
        lookup_expr="lte",
        min_value=0
    )

    category = django_filters.NumberFilter(
        field_name="category_id"
    )

    is_featured = django_filters.BooleanFilter()

    class Meta:
        model = Product
        form = ProductFilterForm
        fields = [
            "category",
            "is_featured",
            "min_price",
            "max_price",
        ]
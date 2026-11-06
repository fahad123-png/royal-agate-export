from django.db import models
from django.core.validators import MinValueValidator
from django.utils.text import slugify
from django.db.models import Q

class Category(models.Model):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    
    class SellingMode(models.TextChoices):
        RETAIL = "RETAIL", "Retail"
        WHOLESALE = "WHOLESALE", "Wholesale"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)

    sku = models.CharField(max_length=100, unique=True)

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products"
    )

    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)

    retail_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.01)]
    )

    wholesale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.01)]
    )
    
    selling_modes = models.JSONField(
        default=list,
        blank=True
    )

    retail_moq = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)]
    )

    wholesale_moq = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)]
    )


    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductImage(models.Model):

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images"
    )

    image_url = models.URLField(max_length=1000)

    alt_text = models.CharField(
        max_length=255,
        blank=True
    )

    sort_order = models.PositiveIntegerField(default=0)

    is_primary = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Product Image"
        verbose_name_plural = "Product Images"

        constraints = [
            models.UniqueConstraint(
                fields=["product"],
                condition=Q(is_primary=True),
                name="unique_primary_image_per_product"
            )
        ]

    def __str__(self):
        return f"{self.product.name} - Image {self.id}"


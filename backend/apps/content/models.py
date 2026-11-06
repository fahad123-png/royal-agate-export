from django.conf import settings
from django.db import models
from django.utils.text import slugify


class ContentPage(models.Model):

    title = models.CharField(max_length=200)

    slug = models.SlugField(
        max_length=220,
        unique=True,
    )

    content = models.TextField()

    seo_title = models.CharField(
        max_length=200,
        blank=True,
    )

    seo_description = models.CharField(
        max_length=320,
        blank=True,
    )

    is_published = models.BooleanField(default=False)

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_content_pages",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        verbose_name = "Content Page"
        verbose_name_plural = "Content Pages"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class FAQCategory(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True,
    )

    slug = models.SlugField(
        max_length=120,
        unique=True,
    )

    is_active = models.BooleanField(default=True)

    sort_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "FAQ Category"
        verbose_name_plural = "FAQ Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class FAQ(models.Model):

    category = models.ForeignKey(
        FAQCategory,
        on_delete=models.PROTECT,
        related_name="faqs",
    )

    question = models.CharField(max_length=300)

    answer = models.TextField()

    is_published = models.BooleanField(default=False)

    sort_order = models.PositiveIntegerField(default=0)

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_faqs",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question
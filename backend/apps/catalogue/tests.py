from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.text import slugify

from rest_framework.test import APIClient

from .models import Category, Product, ProductImage
from apps.inventory.models import Inventory
from .serializers import CategorySerializer, ProductSerializer


User = get_user_model()


class CategoryModelTest(TestCase):

    def test_category_creation(self):
        category = Category.objects.create(name="Agate Stones")

        self.assertEqual(category.name, "Agate Stones")
        self.assertEqual(category.slug, slugify("Agate Stones"))

    def test_category_string_representation(self):
        category = Category.objects.create(name="Gemstones")

        self.assertEqual(str(category), "Gemstones")


class ProductModelTest(TestCase):

    def setUp(self):
        self.category = Category.objects.create(name="Agate Stones")

    def test_product_creation(self):
        product = Product.objects.create(
            name="Natural Agate",
            sku="AGT001",
            category=self.category,
            retail_price=Decimal("1500.00"),
            wholesale_price=Decimal("1200.00"),
        )

        self.assertEqual(product.name, "Natural Agate")
        self.assertEqual(product.category, self.category)
        self.assertEqual(product.slug, slugify("Natural Agate"))

    def test_product_string_representation(self):
        product = Product.objects.create(
            name="Blue Agate",
            sku="AGT002",
            category=self.category,
            retail_price=Decimal("2000.00"),
        )

        self.assertEqual(str(product), "Blue Agate")


class CategorySerializerTest(TestCase):

    def test_valid_category(self):
        serializer = CategorySerializer(data={
            "name": "Crystal Stones",
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_empty_category_name(self):
        serializer = CategorySerializer(data={
            "name": "   ",
        })

        self.assertFalse(serializer.is_valid())


class ProductSerializerTest(TestCase):

    def setUp(self):
        self.category = Category.objects.create(name="Agate Stones")

    def get_valid_data(self):
        return {
            "name": "Natural Agate",
            "sku": "AGT001",
            "category": self.category.id,
            "retail_price": "1500.00",
            "wholesale_price": "1200.00",
            "selling_modes": ["RETAIL", "WHOLESALE"],
            "retail_moq": 1,
            "wholesale_moq": 20,
        }

    def test_valid_product(self):
        serializer = ProductSerializer(data=self.get_valid_data())

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_negative_retail_price(self):
        data = self.get_valid_data()
        data["retail_price"] = "-100"

        serializer = ProductSerializer(data=data)

        self.assertFalse(serializer.is_valid())

    def test_negative_wholesale_price(self):
        data = self.get_valid_data()
        data["wholesale_price"] = "-100"

        serializer = ProductSerializer(data=data)

        self.assertFalse(serializer.is_valid())

    def test_inactive_category_rejected(self):
        self.category.is_active = False
        self.category.save()

        serializer = ProductSerializer(data=self.get_valid_data())

        self.assertFalse(serializer.is_valid())
        self.assertIn("category", serializer.errors)

    def test_sku_is_converted_to_uppercase(self):
        data = self.get_valid_data()
        data["sku"] = "agt001"

        serializer = ProductSerializer(data=data)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["sku"], "AGT001")

    def test_duplicate_sku_rejected(self):
        Product.objects.create(
            name="Existing Agate",
            sku="AGT001",
            category=self.category,
            retail_price=Decimal("1500.00"),
        )

        data = self.get_valid_data()
        data["name"] = "Another Agate"

        serializer = ProductSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("sku", serializer.errors)

    def test_retail_only_product(self):
        data = self.get_valid_data()

        data["selling_modes"] = ["RETAIL"]
        data["wholesale_price"] = None
        data["wholesale_moq"] = None

        serializer = ProductSerializer(data=data)

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_wholesale_only_product(self):
        data = self.get_valid_data()

        data["selling_modes"] = ["WHOLESALE"]
        data["retail_price"] = None
        data["retail_moq"] = None

        serializer = ProductSerializer(data=data)

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_retail_mode_requires_retail_price(self):
        data = self.get_valid_data()
        data["retail_price"] = None

        serializer = ProductSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("retail_price", serializer.errors)

    def test_wholesale_mode_requires_wholesale_moq(self):
        data = self.get_valid_data()
        data["wholesale_moq"] = None

        serializer = ProductSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("wholesale_moq", serializer.errors)

    def test_empty_selling_modes_rejected(self):
        data = self.get_valid_data()
        data["selling_modes"] = []

        serializer = ProductSerializer(data=data)

        self.assertFalse(serializer.is_valid())


class CatalogueAPITest(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.category = Category.objects.create(
            name="Agate Stones"
        )

        self.inactive_category = Category.objects.create(
            name="Inactive Category",
            is_active=False
        )

        self.product = Product.objects.create(
            name="Natural Agate",
            sku="AGT001",
            category=self.category,
            retail_price=Decimal("1500.00"),
            is_featured=True,
        )

        self.inactive_product = Product.objects.create(
            name="Hidden Agate",
            sku="AGT002",
            category=self.category,
            retail_price=Decimal("2000.00"),
            is_active=False,
        )

        self.admin = User.objects.create_user(
            username="catalogueadmin",
            password="TestPassword123!",
            is_staff=True,
        )

    def test_public_can_view_categories(self):
        response = self.client.get(reverse("category-list"))

        self.assertEqual(response.status_code, 200)

    def test_public_can_view_active_products(self):
        response = self.client.get(reverse("product-list"))

        self.assertEqual(response.status_code, 200)

        product_ids = [
            item["id"] for item in response.data["results"]
        ]

        self.assertIn(self.product.id, product_ids)
        self.assertNotIn(self.inactive_product.id, product_ids)

    def test_anonymous_cannot_create_category(self):
        response = self.client.post(
            reverse("category-list"),
            {"name": "New Category"}
        )

        self.assertIn(response.status_code, [401, 403])

    def test_admin_can_create_category(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse("category-list"),
            {"name": "New Category"}
        )

        self.assertEqual(response.status_code, 201)

    def test_anonymous_cannot_create_product(self):
        response = self.client.post(
            reverse("product-list"),
            {
                "name": "New Product",
                "sku": "AGT003",
                "category": self.category.id,
                "retail_price": "1000.00",
            }
        )

        self.assertIn(response.status_code, [401, 403])

    def test_product_search(self):
        response = self.client.get(
            reverse("product-list"),
            {"search": "Natural Agate"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_featured_product_filter(self):
        response = self.client.get(
            reverse("product-list"),
            {"is_featured": "true"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_price_filter(self):
        response = self.client.get(
            reverse("product-list"),
            {
                "min_price": "1000",
                "max_price": "1800",
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_inactive_category_not_visible_publicly(self):
        response = self.client.get(reverse("category-list"))

        self.assertEqual(response.status_code, 200)

        category_ids = [
            item["id"] for item in response.data["results"]
        ]

        self.assertNotIn(
            self.inactive_category.id,
            category_ids
        )

    def test_invalid_price_range_returns_400(self):
        response = self.client.get(
            reverse("product-list"),
            {
                "min_price": "2000",
                "max_price": "1000",
            }
        )

        self.assertEqual(response.status_code, 400)

    def test_product_ordering(self):
        Product.objects.create(
            name="Blue Agate",
            sku="AGT003",
            category=self.category,
            retail_price=Decimal("1800.00"),
        )

        response = self.client.get(
            reverse("product-list"),
            {"ordering": "name"}
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["results"][0]["name"],
            "Blue Agate"
        )

    def test_product_pagination(self):
        for i in range(13):
            Product.objects.create(
                name=f"Test Agate {i}",
                sku=f"TEST{i:03d}",
                category=self.category,
                retail_price=Decimal("1000.00"),
            )

        response = self.client.get(
            reverse("product-list")
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 12)

    def test_custom_page_size(self):
        for i in range(5):
            Product.objects.create(
                name=f"Custom Agate {i}",
                sku=f"CUST{i:03d}",
                category=self.category,
                retail_price=Decimal("1000.00"),
            )

        response = self.client.get(
            reverse("product-list"),
            {"page_size": 2}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 2)
        
class ProductDetailAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.category = Category.objects.create(
            name="Premium Agate"
        )

        self.product = Product.objects.create(
            name="Natural Blue Agate",
            sku="BLUE001",
            category=self.category,
            retail_price=Decimal("1500.00"),
            wholesale_price=Decimal("1200.00"),
            selling_modes=["RETAIL", "WHOLESALE"],
            retail_moq=1,
            wholesale_moq=20,
        )

        self.detail_url = reverse(
            "product-detail",
            kwargs={"pk": self.product.id}
        )

    def test_public_can_view_product_detail(self):
        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["name"],
            "Natural Blue Agate"
        )

    def test_product_detail_contains_images(self):
        ProductImage.objects.create(
            product=self.product,
            image_url="https://example.com/agate-front.jpg",
            alt_text="Front view",
            sort_order=1,
            is_primary=True,
        )

        ProductImage.objects.create(
            product=self.product,
            image_url="https://example.com/agate-side.jpg",
            alt_text="Side view",
            sort_order=2,
            is_primary=False,
        )

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["images"]), 2)

        self.assertEqual(
            response.data["images"][0]["alt_text"],
            "Front view"
        )

        self.assertTrue(
            response.data["images"][0]["is_primary"]
        )

    def test_product_without_inventory(self):
        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["stock_quantity"], 0)
        self.assertFalse(response.data["is_in_stock"])
        self.assertFalse(response.data["is_low_stock"])
        self.assertFalse(response.data["retail_available"])
        self.assertFalse(response.data["wholesale_available"])

    def test_product_with_zero_stock(self):
        Inventory.objects.create(
            product=self.product,
            quantity=0,
            low_stock_threshold=5,
        )

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["stock_quantity"], 0)
        self.assertFalse(response.data["is_in_stock"])
        self.assertFalse(response.data["retail_available"])
        self.assertFalse(response.data["wholesale_available"])

    def test_retail_available_when_stock_meets_retail_moq(self):
        Inventory.objects.create(
            product=self.product,
            quantity=1,
            low_stock_threshold=5,
        )

        response = self.client.get(self.detail_url)

        self.assertTrue(response.data["is_in_stock"])
        self.assertTrue(response.data["retail_available"])
        self.assertFalse(response.data["wholesale_available"])

    def test_wholesale_unavailable_below_wholesale_moq(self):
        Inventory.objects.create(
            product=self.product,
            quantity=19,
            low_stock_threshold=5,
        )

        response = self.client.get(self.detail_url)

        self.assertTrue(response.data["retail_available"])
        self.assertFalse(response.data["wholesale_available"])

    def test_wholesale_available_when_stock_meets_moq(self):
        Inventory.objects.create(
            product=self.product,
            quantity=20,
            low_stock_threshold=5,
        )

        response = self.client.get(self.detail_url)

        self.assertTrue(response.data["retail_available"])
        self.assertTrue(response.data["wholesale_available"])

    def test_low_stock_status(self):
        Inventory.objects.create(
            product=self.product,
            quantity=3,
            low_stock_threshold=5,
        )

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_low_stock"])

    def test_inactive_product_detail_not_publicly_accessible(self):
        self.product.is_active = False
        self.product.save()

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 404)
        
class ProductImageAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.category = Category.objects.create(
            name="Premium Agate"
        )

        self.product = Product.objects.create(
            name="Natural Blue Agate",
            sku="BLUE001",
            category=self.category,
            retail_price=Decimal("1500.00"),
            selling_modes=["RETAIL"],
            retail_moq=1,
        )

        self.admin = User.objects.create_user(
            username="imageadmin",
            password="TestPassword123!",
            is_staff=True,
        )

        self.customer = User.objects.create_user(
            username="imagecustomer",
            password="TestPassword123!",
        )

        self.list_url = reverse("product-image-list")

        self.image = ProductImage.objects.create(
            product=self.product,
            image_url="https://example.com/agate-front.jpg",
            alt_text="Front view",
            sort_order=1,
            is_primary=True,
        )

        self.detail_url = reverse(
            "product-image-detail",
            kwargs={"pk": self.image.id}
        )

    def test_admin_can_list_product_images(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)

    def test_admin_can_create_product_image(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            self.list_url,
            {
                "product": self.product.id,
                "image_url": "https://example.com/agate-side.jpg",
                "alt_text": "Side view",
                "sort_order": 2,
                "is_primary": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(ProductImage.objects.count(), 2)

    def test_admin_can_update_product_image(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            self.detail_url,
            {"alt_text": "Updated front view"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.image.refresh_from_db()

        self.assertEqual(
            self.image.alt_text,
            "Updated front view"
        )

    def test_admin_can_delete_product_image(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            ProductImage.objects.filter(pk=self.image.id).exists()
        )

    def test_customer_cannot_manage_product_images(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_cannot_manage_product_images(self):
        response = self.client.get(self.list_url)

        self.assertIn(response.status_code, [401, 403])

    def test_duplicate_primary_image_returns_400(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            self.list_url,
            {
                "product": self.product.id,
                "image_url": "https://example.com/agate-back.jpg",
                "alt_text": "Back view",
                "sort_order": 2,
                "is_primary": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(ProductImage.objects.count(), 1)
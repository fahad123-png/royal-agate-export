from decimal import Decimal
from rest_framework.exceptions import ValidationError

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from rest_framework import status
from rest_framework.test import APITestCase, APIClient, APIRequestFactory

from apps.accounts.models import CustomerProfile
from apps.catalogue.models import Category, Product, ProductImage
from apps.inventory.models import Inventory

from .models import Cart, CartItem, CustomerAddress
from .serializers import CartSerializer, CustomerAddressSerializer
from .services import CartService


User = get_user_model()


# ============================================================
# TEST FACTORY
# ============================================================

class CartTestFactory:

    def create_user(self, email="customer@example.com", is_staff=False):
        user = User.objects.create_user(
            username=email.split("@")[0],
            email=email,
            password="StrongPassword@123",
            is_staff=is_staff
        )

        if not is_staff:
            CustomerProfile.objects.create(
                user=user,
                phone_number="9876543210"
            )

        return user

    def create_category(self):
        return Category.objects.create(
            name="Gemstones",
            description="Premium gemstones",
            is_active=True
        )

    def create_product(
        self,
        category,
        name="Ruby Stone",
        sku="RUBY-001",
        retail_price=Decimal("100.00"),
        wholesale_price=Decimal("80.00"),
        selling_modes=None,
        retail_moq=None,
        wholesale_moq=None,
        is_active=True
    ):

        if selling_modes is None:
            selling_modes = ["RETAIL", "WHOLESALE"]

        return Product.objects.create(
            name=name,
            sku=sku,
            category=category,
            retail_price=retail_price,
            wholesale_price=wholesale_price,
            selling_modes=selling_modes,
            retail_moq=retail_moq,
            wholesale_moq=wholesale_moq,
            is_active=is_active
        )

    def create_inventory(self, product, quantity=100):
        return Inventory.objects.create(
            product=product,
            quantity=quantity,
            low_stock_threshold=5
        )

    def create_address(self, user, is_default=False):
        return CustomerAddress.objects.create(
            user=user,
            full_name="Test Customer",
            phone_number="9876543210",
            address_line_1="123 Test Street",
            address_line_2="Near Market",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380001",
            country="India",
            is_default=is_default
        )


# ============================================================
# CART MODEL TESTS
# ============================================================

class CartModelTests(CartTestFactory, TestCase):

    def setUp(self):
        self.user = self.create_user()

    def test_create_cart(self):
        cart = Cart.objects.create(user=self.user)

        self.assertEqual(cart.user, self.user)
        self.assertIsNotNone(cart.created_at)

    def test_one_cart_per_customer(self):
        Cart.objects.create(user=self.user)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Cart.objects.create(user=self.user)

    def test_cart_string_representation(self):
        cart = Cart.objects.create(user=self.user)

        self.assertIn("Cart", str(cart))


# ============================================================
# CART ITEM MODEL TESTS
# ============================================================

class CartItemModelTests(CartTestFactory, TestCase):

    def setUp(self):
        self.user = self.create_user()
        self.category = self.create_category()

        self.product = self.create_product(self.category)
        self.create_inventory(self.product)

        self.cart = Cart.objects.create(user=self.user)

    def test_create_cart_item(self):
        item = CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            purchase_mode=CartItem.PurchaseMode.RETAIL,
            quantity=2
        )

        self.assertEqual(item.quantity, 2)

    def test_same_product_same_mode_unique_constraint(self):
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            purchase_mode="RETAIL",
            quantity=2
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CartItem.objects.create(
                    cart=self.cart,
                    product=self.product,
                    purchase_mode="RETAIL",
                    quantity=3
                )

    def test_same_product_different_modes_allowed(self):
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            purchase_mode="RETAIL",
            quantity=2
        )

        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            purchase_mode="WHOLESALE",
            quantity=10
        )

        self.assertEqual(
            CartItem.objects.filter(
                cart=self.cart,
                product=self.product
            ).count(),
            2
        )

    def test_quantity_zero_rejected_by_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CartItem.objects.create(
                    cart=self.cart,
                    product=self.product,
                    purchase_mode="RETAIL",
                    quantity=0
                )
                
    def test_invalid_purchase_mode_rejected_by_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CartItem.objects.create(
                    cart=self.cart,
                    product=self.product,
                    purchase_mode="INVALID",
                    quantity=2
                )


# ============================================================
# CART SERVICE TESTS
# ============================================================

class CartServiceTests(CartTestFactory, TestCase):

    def setUp(self):
        self.user = self.create_user()

        self.category = self.create_category()

        self.product = self.create_product(
            self.category
        )

        self.inventory = self.create_inventory(
            self.product,
            quantity=100
        )

    def test_get_or_create_cart(self):
        cart = CartService.get_or_create_cart(self.user)

        self.assertEqual(cart.user, self.user)

    def test_get_existing_cart(self):
        cart1 = CartService.get_or_create_cart(self.user)
        cart2 = CartService.get_or_create_cart(self.user)

        self.assertEqual(cart1.id, cart2.id)

    def test_add_retail_item(self):
        item, created = CartService.add_item(
            self.user,
            self.product.id,
            "RETAIL",
            2
        )

        self.assertTrue(created)
        self.assertEqual(item.quantity, 2)

    def test_add_wholesale_item(self):
        item, created = CartService.add_item(
            self.user,
            self.product.id,
            "WHOLESALE",
            10
        )

        self.assertTrue(created)
        self.assertEqual(item.quantity, 10)

    def test_duplicate_item_updates_quantity(self):
        CartService.add_item(
            self.user,
            self.product.id,
            "RETAIL",
            2
        )

        item, created = CartService.add_item(
            self.user,
            self.product.id,
            "RETAIL",
            3
        )

        self.assertFalse(created)
        self.assertEqual(item.quantity, 5)

        self.assertEqual(
            CartItem.objects.filter(
                cart__user=self.user,
                product=self.product,
                purchase_mode="RETAIL"
            ).count(),
            1
        )

    def test_retail_and_wholesale_are_separate_items(self):
        CartService.add_item(
            self.user,
            self.product.id,
            "RETAIL",
            2
        )

        CartService.add_item(
            self.user,
            self.product.id,
            "WHOLESALE",
            10
        )

        self.assertEqual(
            CartItem.objects.filter(
                cart__user=self.user,
                product=self.product
            ).count(),
            2
        )

    def test_inactive_product_rejected(self):
        self.product.is_active = False
        self.product.save()

        with self.assertRaises(ValidationError):
            CartService.add_item(
                self.user,
                self.product.id,
                "RETAIL",
                2
            )

    def test_nonexistent_product_rejected(self):
        with self.assertRaises(ValidationError):
            CartService.add_item(
                self.user,
                999999,
                "RETAIL",
                2
            )

    def test_unsupported_purchase_mode_rejected(self):
        with self.assertRaises(ValidationError):
            CartService.add_item(
                self.user,
                self.product.id,
                "WHOLESALE_INVALID",
                10
            )

    def test_retail_mode_not_available(self):
        self.product.selling_modes = ["WHOLESALE"]
        self.product.save()

        with self.assertRaises(ValidationError):
            CartService.add_item(
                self.user,
                self.product.id,
                "RETAIL",
                2
            )

    def test_wholesale_mode_not_available(self):
        self.product.selling_modes = ["RETAIL"]
        self.product.save()

        with self.assertRaises(ValidationError):
            CartService.add_item(
                self.user,
                self.product.id,
                "WHOLESALE",
                10
            )

    def test_missing_retail_price_rejected(self):
        self.product.retail_price = None
        self.product.save()

        with self.assertRaises(ValidationError):
            CartService.add_item(
                self.user,
                self.product.id,
                "RETAIL",
                2
            )

    def test_missing_wholesale_price_rejected(self):
        self.product.wholesale_price = None
        self.product.save()

        with self.assertRaises(ValidationError):
            CartService.add_item(
                self.user,
                self.product.id,
                "WHOLESALE",
                10
            )

    def test_default_retail_moq(self):
        with self.assertRaises(ValidationError):
            CartService.add_item(
                self.user,
                self.product.id,
                "RETAIL",
                0
            )

    def test_default_wholesale_moq(self):
        with self.assertRaises(ValidationError):
            CartService.add_item(
                self.user,
                self.product.id,
                "WHOLESALE",
                9
            )

    def test_custom_retail_moq(self):
        self.product.retail_moq = 5
        self.product.save()

        with self.assertRaises(ValidationError):
            CartService.add_item(
                self.user,
                self.product.id,
                "RETAIL",
                4
            )

    def test_custom_wholesale_moq(self):
        self.product.wholesale_moq = 20
        self.product.save()

        with self.assertRaises(ValidationError):
            CartService.add_item(
                self.user,
                self.product.id,
                "WHOLESALE",
                19
            )

    def test_sufficient_stock(self):
        item, _ = CartService.add_item(
            self.user,
            self.product.id,
            "RETAIL",
            50
        )

        self.assertEqual(item.quantity, 50)

    def test_insufficient_stock(self):
        with self.assertRaises(ValidationError):
            CartService.add_item(
                self.user,
                self.product.id,
                "RETAIL",
                101
            )

    def test_missing_inventory_rejected(self):
        self.inventory.delete()

        with self.assertRaises(ValidationError):
            CartService.add_item(
                self.user,
                self.product.id,
                "RETAIL",
                2
            )

    def test_combined_retail_and_wholesale_stock_validation(self):
        CartService.add_item(
            self.user,
            self.product.id,
            "RETAIL",
            60
        )

        with self.assertRaises(ValidationError):
            CartService.add_item(
                self.user,
                self.product.id,
                "WHOLESALE",
                50
            )

    def test_update_item_quantity(self):
        item, _ = CartService.add_item(
            self.user,
            self.product.id,
            "RETAIL",
            2
        )

        updated_item = CartService.update_item(
            self.user,
            item.id,
            5
        )

        self.assertEqual(updated_item.quantity, 5)

    def test_update_item_respects_stock(self):
        item, _ = CartService.add_item(
            self.user,
            self.product.id,
            "RETAIL",
            2
        )

        with self.assertRaises(ValidationError):
            CartService.update_item(
                self.user,
                item.id,
                101
            )

    def test_update_item_respects_combined_stock(self):
        retail_item, _ = CartService.add_item(
            self.user,
            self.product.id,
            "RETAIL",
            50
        )

        CartService.add_item(
            self.user,
            self.product.id,
            "WHOLESALE",
            30
        )

        with self.assertRaises(ValidationError):
            CartService.update_item(
                self.user,
                retail_item.id,
                80
            )

    def test_remove_item(self):
        item, _ = CartService.add_item(
            self.user,
            self.product.id,
            "RETAIL",
            2
        )

        CartService.remove_item(self.user, item.id)

        self.assertFalse(
            CartItem.objects.filter(id=item.id).exists()
        )

    def test_remove_nonexistent_item_rejected(self):
        with self.assertRaises(ValidationError):
            CartService.remove_item(self.user, 999999)

    def test_customer_cannot_remove_another_customers_item(self):
        other_user = self.create_user(
            email="other@example.com"
        )

        item, _ = CartService.add_item(
            other_user,
            self.product.id,
            "RETAIL",
            2
        )

        with self.assertRaises(ValidationError):
            CartService.remove_item(self.user, item.id)

        self.assertTrue(
            CartItem.objects.filter(id=item.id).exists()
        )

    def test_clear_cart(self):
        CartService.add_item(
            self.user,
            self.product.id,
            "RETAIL",
            2
        )

        CartService.clear_cart(self.user)

        self.assertEqual(
            CartItem.objects.filter(
                cart__user=self.user
            ).count(),
            0
        )

    def test_clear_cart_does_not_affect_other_customer(self):
        other_user = self.create_user(
            email="other@example.com"
        )

        CartService.add_item(
            self.user,
            self.product.id,
            "RETAIL",
            2
        )

        CartService.add_item(
            other_user,
            self.product.id,
            "RETAIL",
            3
        )

        CartService.clear_cart(self.user)

        self.assertEqual(
            CartItem.objects.filter(
                cart__user=other_user
            ).count(),
            1
        )


# ============================================================
# CART API TESTS
# ============================================================

class CartAPITests(CartTestFactory, APITestCase):

    def setUp(self):
        self.user = self.create_user()

        self.category = self.create_category()

        self.product = self.create_product(
            self.category
        )

        self.create_inventory(
            self.product,
            quantity=100
        )

        self.cart_url = "/api/v1/cart/"
        self.add_url = "/api/v1/cart/items/"
        self.clear_url = "/api/v1/cart/clear/"

        self.client.force_authenticate(user=self.user)

    def add_item(self, quantity=2, mode="RETAIL"):
        return self.client.post(
            self.add_url,
            {
                "product_id": self.product.id,
                "purchase_mode": mode,
                "quantity": quantity
            },
            format="json"
        )

    def test_get_cart(self):
        response = self.client.get(self.cart_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertIn("items", response.data)
        self.assertIn("total_amount", response.data)

    def test_add_item_api(self):
        response = self.add_item()

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

    def test_duplicate_add_returns_200(self):
        self.add_item(quantity=2)

        response = self.add_item(quantity=3)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(response.data["item"]["quantity"], 5)

    def test_add_wholesale_item_api(self):
        response = self.add_item(
            quantity=10,
            mode="WHOLESALE"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

    def test_invalid_product_id(self):
        response = self.client.post(
            self.add_url,
            {
                "product_id": 999999,
                "purchase_mode": "RETAIL",
                "quantity": 2
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_invalid_quantity(self):
        response = self.add_item(quantity=0)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_missing_product_id(self):
        response = self.client.post(
            self.add_url,
            {
                "purchase_mode": "RETAIL",
                "quantity": 2
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_invalid_purchase_mode(self):
        response = self.client.post(
            self.add_url,
            quantity=2,
            mode="INVALID"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_update_cart_item_api(self):
        add_response = self.add_item()

        item_id = add_response.data["item"]["id"]

        response = self.client.patch(
            f"{self.add_url}{item_id}/",
            {"quantity": 5},
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(response.data["item"]["quantity"], 5)

    def test_delete_cart_item_api(self):
        add_response = self.add_item()

        item_id = add_response.data["item"]["id"]

        response = self.client.delete(
            f"{self.add_url}{item_id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

    def test_clear_cart_api(self):
        self.add_item()

        response = self.client.delete(self.clear_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            CartItem.objects.filter(
                cart__user=self.user
            ).count(),
            0
        )

    def test_anonymous_user_cannot_access_cart(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.cart_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_anonymous_user_cannot_add_item(self):
        self.client.force_authenticate(user=None)

        response = self.add_item()

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_staff_user_cannot_access_customer_cart(self):
        staff = self.create_user(
            email="staff@example.com",
            is_staff=True
        )

        self.client.force_authenticate(user=staff)

        response = self.client.get(self.cart_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_customer_cannot_access_another_customer_cart(self):
        other_user = self.create_user(
            email="other@example.com"
        )

        CartService.add_item(
            other_user,
            self.product.id,
            "RETAIL",
            2
        )

        response = self.client.get(self.cart_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(len(response.data["items"]), 0)


# ============================================================
# CART SERIALIZER TESTS
# ============================================================

class CartSerializerTests(CartTestFactory, TestCase):

    def setUp(self):
        self.user = self.create_user()
        self.category = self.create_category()

        self.product = self.create_product(self.category)

        self.create_inventory(self.product)

        self.cart = Cart.objects.create(user=self.user)

    def test_cart_total_quantity(self):
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            purchase_mode="RETAIL",
            quantity=3
        )

        serializer = CartSerializer(self.cart)

        self.assertEqual(serializer.data["total_items"], 3)

    def test_cart_total_amount(self):
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            purchase_mode="RETAIL",
            quantity=2
        )

        serializer = CartSerializer(self.cart)

        self.assertEqual(
            serializer.data["total_amount"],
            Decimal("200.00")
        )

    def test_wholesale_total_amount(self):
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            purchase_mode="WHOLESALE",
            quantity=10
        )

        serializer = CartSerializer(self.cart)

        self.assertEqual(
            serializer.data["total_amount"],
            Decimal("800.00")
        )

    def test_product_without_image(self):
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            purchase_mode="RETAIL",
            quantity=1
        )

        serializer = CartSerializer(self.cart)

        self.assertIsNone(
            serializer.data["items"][0]["product_image"]
        )

    def test_primary_product_image(self):
        image = ProductImage.objects.create(
            product=self.product,
            image_url="https://example.com/ruby.jpg",
            alt_text="Ruby",
            is_primary=True
        )

        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            purchase_mode="RETAIL",
            quantity=1
        )

        serializer = CartSerializer(self.cart)

        self.assertEqual(
            serializer.data["items"][0]["product_image"],
            image.image_url
        )


# ============================================================
# CUSTOMER ADDRESS MODEL TESTS
# ============================================================

class CustomerAddressModelTests(CartTestFactory, TestCase):

    def setUp(self):
        self.user = self.create_user()

    def test_create_address(self):
        address = self.create_address(self.user)

        self.assertEqual(address.user, self.user)
        self.assertEqual(address.city, "Ahmedabad")

    def test_one_default_address_per_customer(self):
        self.create_address(self.user, is_default=True)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_address(self.user, is_default=True)

    def test_multiple_non_default_addresses_allowed(self):
        self.create_address(self.user)
        self.create_address(self.user)

        self.assertEqual(
            CustomerAddress.objects.filter(
                user=self.user
            ).count(),
            2
        )


# ============================================================
# CUSTOMER ADDRESS SERIALIZER TESTS
# ============================================================

class CustomerAddressSerializerTests(CartTestFactory, TestCase):

    def setUp(self):
        self.user = self.create_user()
        self.factory = APIRequestFactory()

        self.request = self.factory.post("/")

        self.request.user = self.user

        self.context = {
            "request": self.request
        }

    def get_address_data(self, is_default=False):
        return {
            "full_name": "Test Customer",
            "phone_number": "9876543210",
            "address_line_1": "123 Test Street",
            "address_line_2": "",
            "city": "Ahmedabad",
            "state": "Gujarat",
            "pincode": "380001",
            "country": "India",
            "is_default": is_default
        }

    def test_create_address_serializer(self):
        serializer = CustomerAddressSerializer(
            data=self.get_address_data(),
            context=self.context
        )

        self.assertTrue(serializer.is_valid())

        address = serializer.save()

        self.assertEqual(address.user, self.user)

    def test_create_default_address(self):
        serializer = CustomerAddressSerializer(
            data=self.get_address_data(is_default=True),
            context=self.context
        )

        self.assertTrue(serializer.is_valid())

        address = serializer.save()

        self.assertTrue(address.is_default)

    def test_switch_default_address(self):
        old_address = self.create_address(
            self.user,
            is_default=True
        )

        serializer = CustomerAddressSerializer(
            data=self.get_address_data(is_default=True),
            context=self.context
        )

        self.assertTrue(serializer.is_valid())

        new_address = serializer.save()

        old_address.refresh_from_db()

        self.assertFalse(old_address.is_default)
        self.assertTrue(new_address.is_default)

    def test_update_default_address(self):
        address = self.create_address(self.user)

        serializer = CustomerAddressSerializer(
            address,
            data={"is_default": True},
            partial=True,
            context=self.context
        )

        self.assertTrue(serializer.is_valid())

        updated_address = serializer.save()

        self.assertTrue(updated_address.is_default)

    def test_phone_number_is_trimmed(self):
        data = self.get_address_data()
        data["phone_number"] = " 9876543210 "

        serializer = CustomerAddressSerializer(
            data=data,
            context=self.context
        )

        self.assertTrue(serializer.is_valid())

        self.assertEqual(
            serializer.validated_data["phone_number"],
            "9876543210"
        )

    def test_pincode_is_trimmed(self):
        data = self.get_address_data()
        data["pincode"] = " 380001 "

        serializer = CustomerAddressSerializer(
            data=data,
            context=self.context
        )

        self.assertTrue(serializer.is_valid())

        self.assertEqual(
            serializer.validated_data["pincode"],
            "380001"
        )
        
# ============================================================

# CUSTOMER ADDRESS API TESTS

# ============================================================

class CustomerAddressAPITests(CartTestFactory, APITestCase):

    def setUp(self):
        self.user = self.create_user()
        self.other_user = self.create_user(
            email="other@example.com"
        )

        self.address_url = "/api/v1/cart/addresses/"

        self.client.force_authenticate(user=self.user)

    def get_address_data(self, is_default=False):
        return {
            "full_name": "Test Customer",
            "phone_number": "9876543210",
            "address_line_1": "123 Test Street",
            "address_line_2": "Near Market",
            "city": "Ahmedabad",
            "state": "Gujarat",
            "pincode": "380001",
            "country": "India",
            "is_default": is_default
        }

    # ------------------------------------------
    # LIST ADDRESSES
    # ------------------------------------------

    def test_list_customer_addresses(self):
        self.create_address(self.user)
        self.create_address(self.user)

        response = self.client.get(self.address_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(len(response.data), 2)

    def test_customer_only_sees_own_addresses(self):
        self.create_address(self.user)
        self.create_address(self.other_user)

        response = self.client.get(self.address_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(len(response.data), 1)

    # ------------------------------------------
    # CREATE ADDRESS
    # ------------------------------------------

    def test_create_address_api(self):
        response = self.client.post(
            self.address_url,
            self.get_address_data(),
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.assertEqual(
            CustomerAddress.objects.filter(
                user=self.user
            ).count(),
            1
        )

        self.assertIn("address", response.data)

    def test_create_default_address_api(self):
        response = self.client.post(
            self.address_url,
            self.get_address_data(is_default=True),
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.assertTrue(
            CustomerAddress.objects.get(
                user=self.user
            ).is_default
        )

    def test_create_address_with_empty_phone_rejected(self):
        data = self.get_address_data()
        data["phone_number"] = "   "

        response = self.client.post(
            self.address_url,
            data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_create_address_with_empty_pincode_rejected(self):
        data = self.get_address_data()
        data["pincode"] = "   "

        response = self.client.post(
            self.address_url,
            data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    # ------------------------------------------
    # RETRIEVE ADDRESS
    # ------------------------------------------

    def test_retrieve_address_api(self):
        address = self.create_address(self.user)

        response = self.client.get(
            f"{self.address_url}{address.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            response.data["id"],
            address.id
        )

    def test_customer_cannot_retrieve_another_customers_address(self):
        address = self.create_address(self.other_user)

        response = self.client.get(
            f"{self.address_url}{address.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )

    def test_retrieve_nonexistent_address_returns_404(self):
        response = self.client.get(
            f"{self.address_url}999999/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )

    # ------------------------------------------
    # UPDATE ADDRESS
    # ------------------------------------------

    def test_update_address_api(self):
        address = self.create_address(self.user)

        response = self.client.patch(
            f"{self.address_url}{address.id}/",
            {
                "city": "Surat",
                "pincode": "395001"
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        address.refresh_from_db()

        self.assertEqual(address.city, "Surat")
        self.assertEqual(address.pincode, "395001")

    def test_update_address_to_default_api(self):
        old_address = self.create_address(
            self.user,
            is_default=True
        )

        new_address = self.create_address(self.user)

        response = self.client.patch(
            f"{self.address_url}{new_address.id}/",
            {"is_default": True},
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        old_address.refresh_from_db()
        new_address.refresh_from_db()

        self.assertFalse(old_address.is_default)
        self.assertTrue(new_address.is_default)

    def test_customer_cannot_update_another_customers_address(self):
        address = self.create_address(self.other_user)

        response = self.client.patch(
            f"{self.address_url}{address.id}/",
            {"city": "Mumbai"},
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )

        address.refresh_from_db()

        self.assertEqual(address.city, "Ahmedabad")

    # ------------------------------------------
    # DELETE ADDRESS
    # ------------------------------------------

    def test_delete_address_api(self):
        address = self.create_address(self.user)

        response = self.client.delete(
            f"{self.address_url}{address.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT
        )

        self.assertFalse(
            CustomerAddress.objects.filter(
                id=address.id
            ).exists()
        )

    def test_delete_default_address_leaves_no_default(self):
        address = self.create_address(
            self.user,
            is_default=True
        )

        response = self.client.delete(
            f"{self.address_url}{address.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT
        )

        self.assertFalse(
            CustomerAddress.objects.filter(
                user=self.user,
                is_default=True
            ).exists()
        )

    def test_customer_cannot_delete_another_customers_address(self):
        address = self.create_address(self.other_user)

        response = self.client.delete(
            f"{self.address_url}{address.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )

        self.assertTrue(
            CustomerAddress.objects.filter(
                id=address.id
            ).exists()
        )

    # ------------------------------------------
    # PERMISSION TESTS
    # ------------------------------------------

    def test_anonymous_user_cannot_list_addresses(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.address_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_anonymous_user_cannot_create_address(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(
            self.address_url,
            self.get_address_data(),
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_staff_user_cannot_access_customer_addresses(self):
        staff = self.create_user(
            email="staff@example.com",
            is_staff=True
        )

        self.client.force_authenticate(user=staff)

        response = self.client.get(self.address_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

# ============================================================
# CHECKOUT PREVIEW API TESTS
# ============================================================

class CheckoutPreviewAPITests(CartTestFactory, APITestCase):

    def setUp(self):
        self.user = self.create_user()

        self.category = self.create_category()

        self.product = self.create_product(self.category)

        self.inventory = self.create_inventory(
            self.product,
            quantity=100
        )

        self.address = self.create_address(self.user)

        self.checkout_url = "/api/v1/cart/checkout/preview/"
        self.add_url = "/api/v1/cart/items/"

        self.client.force_authenticate(user=self.user)

    def add_cart_item(self, quantity=2, mode="RETAIL"):
        return self.client.post(
            self.add_url,
            {
                "product_id": self.product.id,
                "purchase_mode": mode,
                "quantity": quantity
            },
            format="json"
        )

    def preview_checkout(self, address_id=None):
        return self.client.post(
            self.checkout_url,
            {
                "address_id": address_id or self.address.id
            },
            format="json"
        )

    # ------------------------------------------------
    # SUCCESSFUL CHECKOUT PREVIEW
    # ------------------------------------------------

    def test_checkout_preview_success(self):
        self.add_cart_item(quantity=2)

        response = self.preview_checkout()

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertIn("items", response.data)
        self.assertIn("shipping_address", response.data)
        self.assertIn("subtotal", response.data)
        self.assertIn("total_amount", response.data)

        self.assertEqual(
            Decimal(str(response.data["total_amount"])),
            Decimal("200.00")
        )

    # ------------------------------------------------
    # EMPTY CART
    # ------------------------------------------------

    def test_checkout_preview_empty_cart(self):
        response = self.preview_checkout()

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    # ------------------------------------------------
    # ADDRESS VALIDATION
    # ------------------------------------------------

    def test_checkout_invalid_address(self):
        self.add_cart_item()

        response = self.preview_checkout(address_id=99999)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_checkout_other_users_address(self):
        self.add_cart_item()

        other_user = self.create_user(
            email="other@example.com"
        )

        other_address = self.create_address(other_user)

        response = self.preview_checkout(
            address_id=other_address.id
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    # ------------------------------------------------
    # PRODUCT VALIDATION
    # ------------------------------------------------

    def test_checkout_inactive_product(self):
        self.add_cart_item()

        self.product.is_active = False
        self.product.save(update_fields=["is_active"])

        response = self.preview_checkout()

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_checkout_unsupported_purchase_mode(self):
        self.add_cart_item()

        self.product.selling_modes = ["WHOLESALE"]
        self.product.save(update_fields=["selling_modes"])

        response = self.preview_checkout()

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
    )

    def test_checkout_quantity_below_moq(self):
        self.product.wholesale_moq = 20
        self.product.save(update_fields=["wholesale_moq"])

        self.add_cart_item(quantity=10, mode="WHOLESALE")

        response = self.preview_checkout()

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    # ------------------------------------------------
    # STOCK VALIDATION
    # ------------------------------------------------

    def test_checkout_insufficient_stock(self):
        self.add_cart_item(quantity=5)

        self.inventory.quantity = 3
        self.inventory.save(update_fields=["quantity"])

        response = self.preview_checkout()

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    # ------------------------------------------------
    # CHECKOUT MUST NOT MODIFY STOCK
    # ------------------------------------------------

    def test_checkout_preview_does_not_deduct_stock(self):
        self.add_cart_item(quantity=5)

        original_stock = self.inventory.quantity

        response = self.preview_checkout()

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.quantity,
            original_stock
        )

    # ------------------------------------------------
    # PERMISSION TESTS
    # ------------------------------------------------

    def test_anonymous_user_cannot_preview_checkout(self):
        self.add_cart_item()

        self.client.force_authenticate(user=None)

        response = self.preview_checkout()

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_staff_user_cannot_preview_checkout(self):
        staff = self.create_user(
            email="staff@example.com",
            is_staff=True
        )

        self.client.force_authenticate(user=staff)

        response = self.preview_checkout()

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db import IntegrityError, transaction

from datetime import timedelta
from django.utils import timezone

from rest_framework.test import APIClient

from apps.catalogue.models import Category, Product
from apps.inventory.models import Inventory, StockMovement
from apps.inventory.services import InventoryService


User = get_user_model()


# =====================================================
# INVENTORY MODEL TESTS
# =====================================================

class InventoryModelTests(TestCase):

    def setUp(self):
        self.category = Category.objects.create(
            name="Agate Stones"
        )

        self.product = Product.objects.create(
            name="Blue Agate",
            sku="AGT-001",
            category=self.category,
            retail_price="500.00",
            wholesale_price="400.00"
        )

        self.inventory = Inventory.objects.create(
            product=self.product,
            quantity=10,
            low_stock_threshold=5
        )

    def test_inventory_creation(self):
        self.assertEqual(self.inventory.quantity, 10)
        self.assertEqual(
            self.inventory.low_stock_threshold,
            5
        )

    def test_inventory_string_representation(self):
        self.assertEqual(
            str(self.inventory),
            "Blue Agate - 10 units"
        )

    def test_is_in_stock(self):
        self.assertTrue(self.inventory.is_in_stock)

    def test_is_not_in_stock(self):
        self.inventory.quantity = 0

        self.assertFalse(self.inventory.is_in_stock)

    def test_is_low_stock(self):
        self.inventory.quantity = 5

        self.assertTrue(self.inventory.is_low_stock)

    def test_is_not_low_stock(self):
        self.inventory.quantity = 10

        self.assertFalse(self.inventory.is_low_stock)

    def test_zero_stock_is_not_low_stock(self):
        self.inventory.quantity = 0

        self.assertFalse(self.inventory.is_low_stock)


# =====================================================
# INVENTORY SERVICE TESTS
# =====================================================

class InventoryServiceTests(TestCase):

    def setUp(self):
        self.category = Category.objects.create(
            name="Quartz Stones"
        )

        self.product = Product.objects.create(
            name="White Quartz",
            sku="QRT-001",
            category=self.category,
            retail_price="300.00",
            wholesale_price="250.00"
        )
        
        # ==========================================
    # DATABASE CONSTRAINT TESTS
    # ==========================================

    def test_database_rejects_zero_movement_quantity(self):
        inventory = Inventory.objects.create(
            product=self.product,
            quantity=0
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.create(
                    inventory=inventory,
                    movement_type="INCREASE",
                    quantity=0,
                    stock_before=0,
                    stock_after=0
                )

    def test_database_rejects_invalid_movement_type(self):
        inventory = Inventory.objects.create(
            product=self.product,
            quantity=0
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.create(
                    inventory=inventory,
                    movement_type="INVALID",
                    quantity=1,
                    stock_before=0,
                    stock_after=1
                )

    def test_database_rejects_inconsistent_increase_movement(self):
        inventory = Inventory.objects.create(
            product=self.product,
            quantity=4
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.create(
                    inventory=inventory,
                    movement_type="INCREASE",
                    quantity=5,
                    stock_before=0,
                    stock_after=4
                )

    def test_database_rejects_inconsistent_decrease_movement(self):
        inventory = Inventory.objects.create(
            product=self.product,
            quantity=6
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.create(
                    inventory=inventory,
                    movement_type="DECREASE",
                    quantity=4,
                    stock_before=10,
                    stock_after=7
                )

    def test_database_rejects_decrease_below_zero(self):
        inventory = Inventory.objects.create(
            product=self.product,
            quantity=0
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.create(
                    inventory=inventory,
                    movement_type="DECREASE",
                    quantity=5,
                    stock_before=3,
                    stock_after=0
                )

    def test_increase_stock(self):
        inventory = InventoryService.increase_stock(
            product=self.product,
            quantity=10,
            reason="Initial stock"
        )

        self.assertEqual(inventory.quantity, 10)

    def test_increase_existing_stock(self):
        InventoryService.increase_stock(
            product=self.product,
            quantity=10
        )

        inventory = InventoryService.increase_stock(
            product=self.product,
            quantity=5
        )

        self.assertEqual(inventory.quantity, 15)

    def test_decrease_stock(self):
        InventoryService.increase_stock(
            product=self.product,
            quantity=10
        )

        inventory = InventoryService.decrease_stock(
            product=self.product,
            quantity=4
        )

        self.assertEqual(inventory.quantity, 6)

    def test_stock_cannot_become_negative(self):
        InventoryService.increase_stock(
            product=self.product,
            quantity=5
        )

        with self.assertRaises(ValidationError):
            InventoryService.decrease_stock(
                product=self.product,
                quantity=10
            )

        inventory = Inventory.objects.get(
            product=self.product
        )

        self.assertEqual(inventory.quantity, 5)

    def test_increase_stock_with_zero_quantity(self):
        with self.assertRaises(ValidationError):
            InventoryService.increase_stock(
                product=self.product,
                quantity=0
            )

    def test_increase_stock_with_negative_quantity(self):
        with self.assertRaises(ValidationError):
            InventoryService.increase_stock(
                product=self.product,
                quantity=-5
            )

    def test_decrease_stock_with_zero_quantity(self):
        with self.assertRaises(ValidationError):
            InventoryService.decrease_stock(
                product=self.product,
                quantity=0
            )

    def test_decrease_stock_with_negative_quantity(self):
        with self.assertRaises(ValidationError):
            InventoryService.decrease_stock(
                product=self.product,
                quantity=-5
            )

    def test_decrease_stock_without_inventory(self):
        with self.assertRaises(ValidationError):
            InventoryService.decrease_stock(
                product=self.product,
                quantity=1
            )

    def test_get_stock(self):
        InventoryService.increase_stock(
            product=self.product,
            quantity=8
        )

        inventory = InventoryService.get_stock(
            self.product
        )

        self.assertIsNotNone(inventory)
        self.assertEqual(inventory.quantity, 8)

    def test_get_stock_when_inventory_does_not_exist(self):
        inventory = InventoryService.get_stock(
            self.product
        )

        self.assertIsNone(inventory)

    def test_stock_movement_history(self):
        InventoryService.increase_stock(
            product=self.product,
            quantity=10
        )

        InventoryService.decrease_stock(
            product=self.product,
            quantity=3
        )

        movements = InventoryService.get_stock_movements(
            self.product
        )

        self.assertEqual(movements.count(), 2)

    def test_stock_movement_before_and_after_values(self):
        InventoryService.increase_stock(
            product=self.product,
            quantity=10
        )

        movement = StockMovement.objects.get(
            movement_type=StockMovement.MovementType.INCREASE
        )

        self.assertEqual(movement.stock_before, 0)
        self.assertEqual(movement.stock_after, 10)
        self.assertEqual(movement.quantity, 10)

    def test_decrease_movement_values(self):
        InventoryService.increase_stock(
            product=self.product,
            quantity=10
        )

        InventoryService.decrease_stock(
            product=self.product,
            quantity=4
        )

        movement = StockMovement.objects.get(
            movement_type=StockMovement.MovementType.DECREASE
        )

        self.assertEqual(movement.stock_before, 10)
        self.assertEqual(movement.stock_after, 6)
        self.assertEqual(movement.quantity, 4)

    def test_stock_movement_reason(self):
        InventoryService.increase_stock(
            product=self.product,
            quantity=10,
            reason="New shipment received"
        )

        movement = StockMovement.objects.first()

        self.assertEqual(
            movement.reason,
            "New shipment received"
        )

    def test_every_adjustment_creates_movement(self):
        InventoryService.increase_stock(
            product=self.product,
            quantity=10
        )

        InventoryService.decrease_stock(
            product=self.product,
            quantity=2
        )

        self.assertEqual(
            StockMovement.objects.count(),
            2
        )


# =====================================================
# INVENTORY API TESTS
# =====================================================

class InventoryAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.category = Category.objects.create(
            name="Premium Agate"
        )

        self.product = Product.objects.create(
            name="Red Agate",
            sku="AGT-002",
            category=self.category,
            retail_price="700.00",
            wholesale_price="600.00"
        )

        self.admin_user = User.objects.create_user(
            username="inventoryadmin",
            email="admin@example.com",
            password="TestPassword123",
            is_staff=True
        )

        self.inventory = Inventory.objects.create(
            product=self.product,
            quantity=20,
            low_stock_threshold=5
        )

    def test_inventory_list_requires_admin(self):
        response = self.client.get(
            reverse("inventory-list")
        )

        self.assertIn(response.status_code, [401, 403])

    def test_inventory_list_for_admin(self):
        self.client.force_authenticate(
            user=self.admin_user
        )

        response = self.client.get(
            reverse("inventory-list")
        )

        self.assertEqual(response.status_code, 200)

    def test_stock_movement_list_requires_admin(self):
        response = self.client.get(
            reverse("stock-movement-list")
        )

        self.assertIn(response.status_code, [401, 403])

    def test_stock_movement_list_for_admin(self):
        self.client.force_authenticate(
            user=self.admin_user
        )

        response = self.client.get(
            reverse("stock-movement-list")
        )

        self.assertEqual(response.status_code, 200)

    def test_stock_adjustment_requires_admin(self):
        response = self.client.post(
            reverse("stock-adjustment"),
            {
                "product_id": self.product.id,
                "movement_type": "INCREASE",
                "quantity": 5
            },
            format="json"
        )

        self.assertIn(response.status_code, [401, 403])

    def test_admin_can_increase_stock(self):
        self.client.force_authenticate(
            user=self.admin_user
        )

        response = self.client.post(
            reverse("stock-adjustment"),
            {
                "product_id": self.product.id,
                "movement_type": "INCREASE",
                "quantity": 5,
                "reason": "New stock"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        self.inventory.refresh_from_db()

        self.assertEqual(self.inventory.quantity, 25)

    def test_admin_can_decrease_stock(self):
        self.client.force_authenticate(
            user=self.admin_user
        )

        response = self.client.post(
            reverse("stock-adjustment"),
            {
                "product_id": self.product.id,
                "movement_type": "DECREASE",
                "quantity": 5,
                "reason": "Stock adjustment"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        self.inventory.refresh_from_db()

        self.assertEqual(self.inventory.quantity, 15)

    def test_adjustment_rejects_zero_quantity(self):
        self.client.force_authenticate(
            user=self.admin_user
        )

        response = self.client.post(
            reverse("stock-adjustment"),
            {
                "product_id": self.product.id,
                "movement_type": "INCREASE",
                "quantity": 0
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_adjustment_rejects_invalid_movement_type(self):
        self.client.force_authenticate(
            user=self.admin_user
        )

        response = self.client.post(
            reverse("stock-adjustment"),
            {
                "product_id": self.product.id,
                "movement_type": "INVALID",
                "quantity": 5
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_adjustment_rejects_invalid_product(self):
        self.client.force_authenticate(
            user=self.admin_user
        )

        response = self.client.post(
            reverse("stock-adjustment"),
            {
                "product_id": 99999,
                "movement_type": "INCREASE",
                "quantity": 5
            },
            format="json"
        )

        self.assertEqual(response.status_code, 404)
        
        
        # ==========================================
    # ADDITIONAL INVENTORY API TESTS
    # ==========================================

    def test_decrease_stock_more_than_available_returns_400(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            reverse("stock-adjustment"),
            {
                "product_id": self.product.id,
                "movement_type": "DECREASE",
                "quantity": 25,
                "reason": "Insufficient stock test"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)

        self.inventory.refresh_from_db()

        # Stock should remain unchanged
        self.assertEqual(self.inventory.quantity, 20)

        # No movement should be recorded
        self.assertEqual(StockMovement.objects.count(), 0)


    def test_normal_user_cannot_adjust_stock(self):
        normal_user = User.objects.create_user(
            username="normaluser",
            email="user@example.com",
            password="TestPassword123",
            is_staff=False
        )

        self.client.force_authenticate(user=normal_user)

        response = self.client.post(
            reverse("stock-adjustment"),
            {
                "product_id": self.product.id,
                "movement_type": "INCREASE",
                "quantity": 5
            },
            format="json"
        )

        self.assertEqual(response.status_code, 403)


    def test_inventory_api_is_read_only(self):
        self.client.force_authenticate(user=self.admin_user)

        # POST should not be allowed
        post_response = self.client.post(
            reverse("inventory-list"),
            {},
            format="json"
        )

        self.assertEqual(post_response.status_code, 405)

        # PATCH should not be allowed
        patch_response = self.client.patch(
            reverse(
                "inventory-detail",
                kwargs={"pk": self.inventory.id}
            ),
            {"quantity": 100},
            format="json"
        )

        self.assertEqual(patch_response.status_code, 405)

        # DELETE should not be allowed
        delete_response = self.client.delete(
            reverse(
                "inventory-detail",
                kwargs={"pk": self.inventory.id}
            )
        )

        self.assertEqual(delete_response.status_code, 405)

        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 20)


    def test_stock_movement_api_is_read_only(self):
        self.client.force_authenticate(user=self.admin_user)

        movement = InventoryService.increase_stock(
            product=self.product,
            quantity=5,
            reason="Test movement"
        )

        stock_movement = StockMovement.objects.get(
            inventory=movement
        )

        # POST should not be allowed
        post_response = self.client.post(
            reverse("stock-movement-list"),
            {},
            format="json"
        )

        self.assertEqual(post_response.status_code, 405)

        # PATCH should not be allowed
        patch_response = self.client.patch(
            reverse(
                "stock-movement-detail",
                kwargs={"pk": stock_movement.id}
            ),
            {"quantity": 100},
            format="json"
        )

        self.assertEqual(patch_response.status_code, 405)

        # DELETE should not be allowed
        delete_response = self.client.delete(
            reverse(
                "stock-movement-detail",
                kwargs={"pk": stock_movement.id}
            )
        )

        self.assertEqual(delete_response.status_code, 405)


    def test_successful_adjustment_creates_stock_movement(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            reverse("stock-adjustment"),
            {
                "product_id": self.product.id,
                "movement_type": "INCREASE",
                "quantity": 10,
                "reason": "New shipment received"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        self.inventory.refresh_from_db()

        self.assertEqual(self.inventory.quantity, 30)

        self.assertEqual(StockMovement.objects.count(), 1)

        movement = StockMovement.objects.first()

        self.assertEqual(movement.movement_type, "INCREASE")
        self.assertEqual(movement.quantity, 10)
        self.assertEqual(movement.stock_before, 20)
        self.assertEqual(movement.stock_after, 30)
        self.assertEqual(movement.reason, "New shipment received")
        self.assertEqual(movement.created_by, self.admin_user)
        
        # ==========================================
    # STOCK MOVEMENT API FILTER TESTS
    # ==========================================

    def test_filter_movements_by_increase_type(self):
        self.client.force_authenticate(user=self.admin_user)

        InventoryService.increase_stock(
            product=self.product,
            quantity=5,
            reason="New stock"
        )

        InventoryService.decrease_stock(
            product=self.product,
            quantity=2,
            reason="Stock sold"
        )

        response = self.client.get(
            reverse("stock-movement-list"),
            {"movement_type": "INCREASE"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["movement_type"],
            "INCREASE"
        )

    def test_filter_movements_by_decrease_type(self):
        self.client.force_authenticate(user=self.admin_user)

        InventoryService.increase_stock(
            product=self.product,
            quantity=5
        )

        InventoryService.decrease_stock(
            product=self.product,
            quantity=2
        )

        response = self.client.get(
            reverse("stock-movement-list"),
            {"movement_type": "DECREASE"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_filter_movements_by_product(self):
        self.client.force_authenticate(user=self.admin_user)

        second_product = Product.objects.create(
            name="Green Agate",
            sku="AGT-003",
            category=self.category,
            retail_price="800.00",
            wholesale_price="700.00"
        )

        InventoryService.increase_stock(
            product=self.product,
            quantity=5
        )

        InventoryService.increase_stock(
            product=second_product,
            quantity=10
        )

        response = self.client.get(
            reverse("stock-movement-list"),
            {"product": self.product.id}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["product_sku"],
            self.product.sku
        )

    def test_filter_movements_by_date_range(self):
        self.client.force_authenticate(user=self.admin_user)

        InventoryService.increase_stock(
            product=self.product,
            quantity=5,
            reason="Old movement"
        )

        movement = StockMovement.objects.first()

        yesterday = timezone.now() - timedelta(days=1)

        StockMovement.objects.filter(
            pk=movement.pk
        ).update(created_at=yesterday)

        InventoryService.increase_stock(
            product=self.product,
            quantity=3,
            reason="Today's movement"
        )

        today = timezone.localdate().isoformat()

        response = self.client.get(
            reverse("stock-movement-list"),
            {
                "date_from": today,
                "date_to": today
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_invalid_movement_type_returns_400(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(
            reverse("stock-movement-list"),
            {"movement_type": "INVALID"}
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_product_filter_returns_400(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(
            reverse("stock-movement-list"),
            {"product": "invalid"}
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_date_returns_400(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(
            reverse("stock-movement-list"),
            {"date_from": "invalid-date"}
        )

        self.assertEqual(response.status_code, 400)

    def test_search_movements_by_reason(self):
        self.client.force_authenticate(user=self.admin_user)

        InventoryService.increase_stock(
            product=self.product,
            quantity=5,
            reason="New shipment received"
        )

        response = self.client.get(
            reverse("stock-movement-list"),
            {"search": "shipment"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_order_movements_by_quantity(self):
        self.client.force_authenticate(user=self.admin_user)

        InventoryService.increase_stock(
            product=self.product,
            quantity=5
        )

        InventoryService.increase_stock(
            product=self.product,
            quantity=10
        )

        response = self.client.get(
            reverse("stock-movement-list"),
            {"ordering": "quantity"}
        )

        self.assertEqual(response.status_code, 200)

        quantities = [
            item["quantity"]
            for item in response.data["results"]
        ]

        self.assertEqual(quantities, [5, 10])

    def test_stock_movement_pagination(self):
        self.client.force_authenticate(user=self.admin_user)

        for i in range(25):
            InventoryService.increase_stock(
                product=self.product,
                quantity=1,
                reason=f"Stock batch {i}"
            )

        response = self.client.get(
            reverse("stock-movement-list"),
            {"page": 1, "page_size": 10}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNotNone(response.data["next"])
        
        
    def test_increase_stock_rejects_decimal_quantity(self):
        with self.assertRaises(ValidationError):
            InventoryService.increase_stock(
                product=self.product,
                quantity=1.5
            )

    def test_decrease_stock_rejects_decimal_quantity(self):
        with self.assertRaises(ValidationError):
            InventoryService.decrease_stock(
                product=self.product,
                quantity=1.5
            )

    def test_increase_stock_rejects_boolean_quantity(self):
        with self.assertRaises(ValidationError):
            InventoryService.increase_stock(
                product=self.product,
                quantity=True
            )

    def test_decrease_stock_rejects_boolean_quantity(self):
        with self.assertRaises(ValidationError):
            InventoryService.decrease_stock(
                product=self.product,
                quantity=False
            )


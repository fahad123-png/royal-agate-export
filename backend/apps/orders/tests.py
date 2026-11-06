from decimal import Decimal
from unittest.mock import patch

from apps.inventory.services import InventoryService

from django.db import IntegrityError, transaction

from django.utils import timezone

from rest_framework.exceptions import ValidationError
from apps.inventory.models import Inventory, StockMovement
from apps.orders.models import Order, OrderItem, OrderCancellation, OrderStatusHistory
from apps.orders.services import OrderService

from rest_framework.test import APIClient

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import CustomerProfile
from apps.catalogue.models import Category, Product
from apps.inventory.models import Inventory
from apps.cart.models import Cart, CartItem, CustomerAddress
from apps.payments.models import Payment

from .models import Order, OrderItem 
from .services import OrderService


User = get_user_model()


class OrderServiceTests(TestCase):

    def setUp(self):

        # Create customer
        self.user = User.objects.create_user(
            username="customer",
            email="customer@example.com",
            password="StrongPassword@123"
        )

        CustomerProfile.objects.create(
            user=self.user,
            phone_number="9876543210"
        )

        # Create category
        self.category = Category.objects.create(
            name="Gemstones",
            description="Premium gemstones",
            is_active=True
        )

        # Create product
        self.product = Product.objects.create(
            name="Ruby Stone",
            sku="RUBY-001",
            category=self.category,
            retail_price=Decimal("100.00"),
            wholesale_price=Decimal("80.00"),
            selling_modes=["RETAIL", "WHOLESALE"]
        )

        # Create inventory
        self.inventory = Inventory.objects.create(
            product=self.product,
            quantity=100,
            low_stock_threshold=5
        )

        # Create cart
        self.cart = Cart.objects.create(
            user=self.user
        )

        # Create shipping address
        self.address = CustomerAddress.objects.create(
            user=self.user,
            full_name="Test Customer",
            phone_number="9876543210",
            address_line_1="123 Test Street",
            address_line_2="Near Market",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380001",
            country="India"
        )

        # Add retail item to cart
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            purchase_mode="RETAIL",
            quantity=2
        )
        
        self.client = APIClient()

    def create_order(self):
        return OrderService.create_order(
            user=self.user,
            address_id=self.address.id
        )
        
        # -----------------------------
    # Order Database Integrity Tests
    # -----------------------------

    def test_invalid_order_status_rejected_by_database(self):
        order = self.create_order()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Order.objects.filter(id=order.id).update(
                    status="INVALID"
                )

    def test_invalid_payment_status_rejected_by_database(self):
        order = self.create_order()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Order.objects.filter(id=order.id).update(
                    payment_status="INVALID"
                )

    def test_invalid_purchase_mode_rejected_by_database(self):
        order = self.create_order()
        item = order.items.get()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrderItem.objects.filter(id=item.id).update(
                    purchase_mode="INVALID"
                )
                
    
    def test_incorrect_item_subtotal_rejected_by_database(self):
        order = self.create_order()
        item = order.items.get()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrderItem.objects.filter(id=item.id).update(
                    subtotal=Decimal("199.99")
                )
    

    def test_invalid_cancellation_status_rejected_by_database(self):
        order = self.create_order()

        cancellation = OrderCancellation.objects.create(
            order=order,
            requested_by=self.user,
            reason="Test cancellation."
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrderCancellation.objects.filter(
                    id=cancellation.id
                ).update(status="INVALID")
                
    
    
    def test_approve_cancellation_failure_rolls_back_all_stock_restorations(self):
        order, cancellation, admin_user = (
            self.create_cancellation_request()
        )

        # Create a second product and inventory.
        second_product = Product.objects.create(
            name="Emerald Stone",
            sku="EMERALD-001",
            category=self.category,
            retail_price=Decimal("200.00"),
            selling_modes=["RETAIL"],
        )

        second_inventory = Inventory.objects.create(
            product=second_product,
            quantity=50,
            low_stock_threshold=5,
        )

        # Add a second item to the confirmed order.
        OrderItem.objects.create(
            order=order,
            product=second_product,
            product_name=second_product.name,
            product_sku=second_product.sku,
            purchase_mode="RETAIL",
            quantity=2,
            unit_price=Decimal("200.00"),
            subtotal=Decimal("400.00"),
        )

        self.inventory.refresh_from_db()
        original_first_stock = self.inventory.quantity
        original_second_stock = second_inventory.quantity

        
        original_increase_stock = InventoryService.increase_stock
        call_count = {"value": 0}


        def fail_on_second_increase(*args, **kwargs):
            call_count["value"] += 1

            if call_count["value"] == 2:
                raise RuntimeError(
                    "Simulated stock restoration failure"
                )

            return original_increase_stock(*args, **kwargs)


        with patch(
            "apps.orders.services.InventoryService.increase_stock",
            side_effect=fail_on_second_increase,
        ):
        
        
            with self.assertRaises(RuntimeError):
                OrderService.approve_cancellation(
                    cancellation_id=cancellation.id,
                    admin_user=admin_user,
                )

        order.refresh_from_db()
        cancellation.refresh_from_db()
        self.inventory.refresh_from_db()
        second_inventory.refresh_from_db()

        # Both inventory quantities must remain unchanged.
        self.assertEqual(
            self.inventory.quantity,
            original_first_stock,
        )

        self.assertEqual(
            second_inventory.quantity,
            original_second_stock,
        )

        # Order and cancellation must remain unchanged.
        self.assertEqual(
            order.status,
            Order.OrderStatus.CONFIRMED,
        )

        self.assertIsNone(order.stock_restored_at)

        self.assertEqual(
            cancellation.status,
            OrderCancellation.CancellationStatus.REQUESTED,
        )

        # No INCREASE movement should survive rollback.
        self.assertEqual(
            StockMovement.objects.filter(
                movement_type="INCREASE",
            ).count(),
            0,
        )
        
    

    def test_invalid_history_status_rejected_by_database(self):
        order = self.create_order()

        history = OrderStatusHistory.objects.filter(
            order=order
        ).first()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrderStatusHistory.objects.filter(
                    id=history.id
                ).update(new_status="INVALID")

    def test_successful_order_creation(self):

        order = self.create_order()

        self.assertIsNotNone(order.id)

        self.assertEqual(
            order.user,
            self.user
        )

        self.assertEqual(
            order.status,
            Order.OrderStatus.PENDING
        )

        self.assertEqual(
            order.payment_status,
            Order.PaymentStatus.PENDING
        )

    def test_order_number_is_generated(self):

        order = self.create_order()

        self.assertTrue(
            order.order_number.startswith("RA-")
        )

        self.assertTrue(
            Order.objects.filter(
                order_number=order.order_number
            ).exists()
        )

    def test_shipping_address_snapshot(self):

        order = self.create_order()

        self.address.city = "Mumbai"
        self.address.save()

        order.refresh_from_db()

        self.assertEqual(
            order.shipping_city,
            "Ahmedabad"
        )

        self.assertEqual(
            order.shipping_full_name,
            "Test Customer"
        )

    def test_order_item_snapshot_and_price(self):

        order = self.create_order()

        item = order.items.get()

        self.assertEqual(
            item.product_name,
            "Ruby Stone"
        )

        self.assertEqual(
            item.product_sku,
            "RUBY-001"
        )

        self.assertEqual(
            item.purchase_mode,
            "RETAIL"
        )

        self.assertEqual(
            item.quantity,
            2
        )

        self.assertEqual(
            item.unit_price,
            Decimal("100.00")
        )

        self.assertEqual(
            item.subtotal,
            Decimal("200.00")
        )

    def test_payment_record_created(self):

        order = self.create_order()

        payment = Payment.objects.get(
            order=order
        )

        self.assertEqual(
            payment.amount,
            Decimal("200.00")
        )

        self.assertEqual(
            payment.status,
            Payment.PaymentStatus.PENDING
        )

    def test_cart_cleared_after_order_creation(self):

        self.create_order()

        self.assertEqual(
            CartItem.objects.filter(
                cart=self.cart
            ).count(),
            0
        )

    def test_inventory_not_deducted_during_order_creation(self):

        self.create_order()

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.quantity,
            100
        )

    def test_order_creation_failure_rolls_back_everything(self):

        with patch(
            "apps.orders.services.Payment.objects.create",
            side_effect=RuntimeError("Payment creation failed")
        ):

            with self.assertRaises(RuntimeError):
                self.create_order()

        self.assertEqual(
            Order.objects.filter(
                user=self.user
            ).count(),
            0
        )

        self.assertEqual(
            OrderItem.objects.count(),
            0
        )

        self.assertEqual(
            Payment.objects.count(),
            0
        )

        self.assertEqual(
            CartItem.objects.filter(
                cart=self.cart
            ).count(),
            1
        )
        
        # -----------------------------
    # Order Creation API Tests
    # -----------------------------

    def test_customer_can_create_order_through_api(self):

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/orders/",
            {
                "address_id": self.address.id,
                "notes": "Please handle carefully."
            },
            format="json"
        )

        self.assertEqual(response.status_code, 201)

        self.assertEqual(
            response.data["message"],
            "Order created successfully."
        )

        self.assertEqual(
            response.data["order"]["status"],
            Order.OrderStatus.PENDING
        )

        self.assertEqual(
            response.data["order"]["payment_status"],
            Order.PaymentStatus.PENDING
        )

        self.assertEqual(
            len(response.data["order"]["items"]),
            1
        )

        self.assertTrue(
            Order.objects.filter(user=self.user).exists()
        )

    def test_unauthenticated_user_cannot_create_order(self):

        response = APIClient().post(
            "/api/v1/orders/",
            {
                "address_id": self.address.id
            },
            format="json"
        )

        self.assertEqual(response.status_code, 401)

        self.assertEqual(Order.objects.count(), 0)

    def test_customer_cannot_use_another_users_address(self):

        another_user = User.objects.create_user(
            username="another_customer",
            email="another@example.com",
            password="StrongPassword@123"
        )

        another_address = CustomerAddress.objects.create(
            user=another_user,
            full_name="Another Customer",
            phone_number="9876543211",
            address_line_1="Another Street",
            city="Surat",
            state="Gujarat",
            pincode="395001",
            country="India"
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/orders/",
            {
                "address_id": another_address.id
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)

        self.assertEqual(Order.objects.count(), 0)

    def test_order_cannot_be_created_with_empty_cart(self):

        self.cart.items.all().delete()

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/orders/",
            {
                "address_id": self.address.id
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)

        self.assertEqual(Order.objects.count(), 0)

    def test_order_cannot_be_created_with_invalid_address(self):

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/orders/",
            {
                "address_id": 999999
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)

        self.assertEqual(Order.objects.count(), 0)

    def test_order_creation_api_clears_cart(self):

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/orders/",
            {
                "address_id": self.address.id
            },
            format="json"
        )

        self.assertEqual(response.status_code, 201)

        self.assertEqual(
            CartItem.objects.filter(cart=self.cart).count(),
            0
        )

        self.assertEqual(Payment.objects.count(), 1)
        
        # -----------------------------
    # Order Listing API Tests
    # -----------------------------

    def test_customer_can_list_own_orders(self):

        order = self.create_order()

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/orders/my-orders/")

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data["count"], 1)

        self.assertEqual(
            len(response.data["results"]),
            1
        )

        self.assertEqual(
            response.data["results"][0]["id"],
            order.id
        )

    def test_customer_can_view_own_order_detail(self):

        order = self.create_order()

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/orders/{order.id}/"
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["order_number"],
            order.order_number
        )

        self.assertEqual(
            len(response.data["items"]),
            1
        )

    def test_customer_cannot_view_another_users_order(self):

        order = self.create_order()

        another_user = User.objects.create_user(
            username="another_customer",
            email="another@example.com",
            password="StrongPassword@123"
        )

        self.client.force_authenticate(user=another_user)

        response = self.client.get(
            f"/api/v1/orders/{order.id}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_customer_cannot_list_another_users_orders(self):

        self.create_order()

        another_user = User.objects.create_user(
            username="another_customer",
            email="another@example.com",
            password="StrongPassword@123"
        )

        self.client.force_authenticate(user=another_user)

        response = self.client.get("/api/v1/orders/my-orders/")

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data["count"], 0)

        self.assertEqual(
            len(response.data["results"]),
            0
        )

    def test_unauthenticated_user_cannot_list_orders(self):

        response = APIClient().get(
            "/api/v1/orders/my-orders/"
        )

        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_user_cannot_view_order_detail(self):

        order = self.create_order()

        response = APIClient().get(
            f"/api/v1/orders/{order.id}/"
        )

        self.assertEqual(response.status_code, 401)

    def test_order_detail_returns_purchase_time_snapshots(self):

        order = self.create_order()

        # Change original product details after order creation
        self.product.name = "Updated Ruby Stone"
        self.product.sku = "RUBY-UPDATED"
        self.product.retail_price = Decimal("150.00")
        self.product.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/orders/{order.id}/"
        )

        self.assertEqual(response.status_code, 200)

        item = response.data["items"][0]

        self.assertEqual(
            item["product_name"],
            "Ruby Stone"
        )

        self.assertEqual(
            item["product_sku"],
            "RUBY-001"
        )

        self.assertEqual(
            Decimal(item["unit_price"]),
            Decimal("100.00")
        )

        self.assertEqual(
            Decimal(item["subtotal"]),
            Decimal("200.00")
        )
        
        # -----------------------------
    # Order Confirmation Tests
    # -----------------------------

    def create_admin(self):
        return User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="StrongPassword@123"
        )

    def test_successful_order_confirmation_deducts_stock(self):

        order = self.create_order()
        admin_user = self.create_admin()

        confirmed_order = OrderService.confirm_order(
            order_id=order.id,
            admin_user=admin_user
        )

        self.inventory.refresh_from_db()
        confirmed_order.refresh_from_db()

        self.assertEqual(
            confirmed_order.status,
            Order.OrderStatus.CONFIRMED
        )

        self.assertEqual(
            self.inventory.quantity,
            98
        )

        self.assertIsNotNone(
            confirmed_order.stock_deducted_at
        )

        self.assertEqual(
            StockMovement.objects.filter(
                inventory=self.inventory,
                movement_type="DECREASE"
            ).count(),
            1
        )

    def test_order_cannot_be_confirmed_twice(self):

        order = self.create_order()
        admin_user = self.create_admin()

        OrderService.confirm_order(
            order_id=order.id,
            admin_user=admin_user
        )

        with self.assertRaises(ValidationError):
            OrderService.confirm_order(
                order_id=order.id,
                admin_user=admin_user
            )

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.quantity,
            98
        )

        self.assertEqual(
            StockMovement.objects.filter(
                inventory=self.inventory,
                movement_type="DECREASE"
            ).count(),
            1
        )

    
    def test_confirmation_fails_when_stock_is_insufficient(self):

        # First create order while sufficient stock exists
        order = self.create_order()
        admin_user = self.create_admin()

        # Now reduce stock after order creation
        self.inventory.quantity = 1
        self.inventory.save()

        with self.assertRaises(ValidationError):
            OrderService.confirm_order(
                order_id=order.id,
                admin_user=admin_user
            )

        order.refresh_from_db()
        self.inventory.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.PENDING
        )

        self.assertIsNone(
            order.stock_deducted_at
        )

        self.assertEqual(
            self.inventory.quantity,
            1
        )

        self.assertEqual(
            StockMovement.objects.filter(
                inventory=self.inventory,
                movement_type="DECREASE"
            ).count(),
            0
        )



    def test_confirmation_failure_rolls_back_all_stock_deductions(self):

        order = self.create_order()
        admin_user = self.create_admin()

        # Create another product with insufficient stock
        second_product = Product.objects.create(
            name="Emerald Stone",
            sku="EMERALD-001",
            category=self.category,
            retail_price=Decimal("200.00"),
            selling_modes=["RETAIL"]
        )

        second_inventory = Inventory.objects.create(
            product=second_product,
            quantity=1,
            low_stock_threshold=5
        )

        # Add second order item directly.
        # This simulates stock becoming insufficient after order creation.
        OrderItem.objects.create(
            order=order,
            product=second_product,
            product_name=second_product.name,
            product_sku=second_product.sku,
            purchase_mode="RETAIL",
            quantity=2,
            unit_price=Decimal("200.00"),
            subtotal=Decimal("400.00")
        )

        with self.assertRaises(ValidationError):
            OrderService.confirm_order(
                order_id=order.id,
                admin_user=admin_user
            )

        order.refresh_from_db()
        self.inventory.refresh_from_db()
        second_inventory.refresh_from_db()

        # First product deduction must also roll back
        self.assertEqual(
            self.inventory.quantity,
            100
        )

        self.assertEqual(
            second_inventory.quantity,
            1
        )

        self.assertEqual(
            order.status,
            Order.OrderStatus.PENDING
        )

        self.assertIsNone(
            order.stock_deducted_at
        )

        self.assertEqual(
            StockMovement.objects.filter(
                movement_type="DECREASE"
            ).count(),
            0
        )

    def test_confirmation_fails_if_product_no_longer_exists(self):

        order = self.create_order()
        admin_user = self.create_admin()

        # Delete product; OrderItem.product uses SET_NULL
        self.product.delete()

        with self.assertRaises(ValidationError):
            OrderService.confirm_order(
                order_id=order.id,
                admin_user=admin_user
            )

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.PENDING
        )

        self.assertIsNone(
            order.stock_deducted_at
        )
        
    
    # -----------------------------
    # Admin Order Confirmation API Tests
    # -----------------------------

    def test_admin_can_confirm_pending_order(self):

        order = self.create_order()
        admin_user = self.create_admin()

        self.client.force_authenticate(user=admin_user)

        response = self.client.post(
            f"/api/v1/orders/{order.id}/confirm/"
        )

        order.refresh_from_db()
        self.inventory.refresh_from_db()

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["message"],
            "Order confirmed successfully."
        )

        self.assertEqual(
            order.status,
            Order.OrderStatus.CONFIRMED
        )

        self.assertEqual(
            self.inventory.quantity,
            98
        )

        self.assertIsNotNone(
            order.stock_deducted_at
        )

    def test_customer_cannot_confirm_order(self):

        order = self.create_order()

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            f"/api/v1/orders/{order.id}/confirm/"
        )

        self.assertEqual(response.status_code, 403)

        order.refresh_from_db()
        self.inventory.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.PENDING
        )

        self.assertEqual(
            self.inventory.quantity,
            100
        )

    def test_unauthenticated_user_cannot_confirm_order(self):

        order = self.create_order()

        response = APIClient().post(
            f"/api/v1/orders/{order.id}/confirm/"
        )

        self.assertEqual(response.status_code, 401)

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.PENDING
        )

    def test_admin_cannot_confirm_nonexistent_order(self):

        admin_user = self.create_admin()

        self.client.force_authenticate(user=admin_user)

        response = self.client.post(
            "/api/v1/orders/999999/confirm/"
        )

        self.assertIn(
            response.status_code,
            [400, 404]
        )

    def test_admin_cannot_confirm_already_confirmed_order(self):

        order = self.create_order()
        admin_user = self.create_admin()

        self.client.force_authenticate(user=admin_user)

        first_response = self.client.post(
            f"/api/v1/orders/{order.id}/confirm/"
        )

        second_response = self.client.post(
            f"/api/v1/orders/{order.id}/confirm/"
        )

        self.assertEqual(first_response.status_code, 200)

        self.assertEqual(second_response.status_code, 400)

        self.inventory.refresh_from_db()

        self.assertEqual(
            self.inventory.quantity,
            98
        )

        self.assertEqual(
            StockMovement.objects.filter(
                inventory=self.inventory,
                movement_type="DECREASE"
            ).count(),
            1
        )
        
        # -----------------------------
    # Order Cancellation Service Tests
    # -----------------------------

    def test_pending_order_can_be_cancelled_directly(self):

        order = self.create_order()

        cancellation = OrderService.request_cancellation(
            user=self.user,
            order_id=order.id,
            reason="Ordered by mistake."
        )

        order.refresh_from_db()
        self.inventory.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.CANCELLED
        )

        self.assertEqual(
            cancellation.status,
            OrderCancellation.CancellationStatus.DIRECT_CANCELLED
        )

        self.assertEqual(self.inventory.quantity, 100)

    def test_confirmed_order_cancellation_requires_approval(self):

        order = self.create_order()
        admin_user = self.create_admin()

        OrderService.confirm_order(order.id, admin_user)

        cancellation = OrderService.request_cancellation(
            user=self.user,
            order_id=order.id,
            reason="Customer changed their mind."
        )

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.CONFIRMED
        )

        self.assertEqual(
            cancellation.status,
            OrderCancellation.CancellationStatus.REQUESTED
        )

        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 98)

    def test_admin_can_approve_cancellation_and_restore_stock(self):

        order = self.create_order()
        admin_user = self.create_admin()

        OrderService.confirm_order(order.id, admin_user)

        cancellation = OrderService.request_cancellation(
            user=self.user,
            order_id=order.id,
            reason="Customer requested cancellation."
        )

        OrderService.approve_cancellation(
            cancellation_id=cancellation.id,
            admin_user=admin_user,
            admin_note="Cancellation approved."
        )

        order.refresh_from_db()
        cancellation.refresh_from_db()
        self.inventory.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.CANCELLED
        )

        self.assertEqual(
            cancellation.status,
            OrderCancellation.CancellationStatus.APPROVED
        )

        self.assertEqual(self.inventory.quantity, 100)

        self.assertIsNotNone(order.stock_restored_at)

        self.assertEqual(
            StockMovement.objects.filter(
                inventory=self.inventory,
                movement_type="INCREASE"
            ).count(),
            1
        )

    def test_admin_can_reject_cancellation(self):

        order = self.create_order()
        admin_user = self.create_admin()

        OrderService.confirm_order(order.id, admin_user)

        cancellation = OrderService.request_cancellation(
            user=self.user,
            order_id=order.id,
            reason="Customer requested cancellation."
        )

        OrderService.reject_cancellation(
            cancellation_id=cancellation.id,
            admin_user=admin_user,
            admin_note="Order is already being processed."
        )

        order.refresh_from_db()
        cancellation.refresh_from_db()
        self.inventory.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.CONFIRMED
        )

        self.assertEqual(
            cancellation.status,
            OrderCancellation.CancellationStatus.REJECTED
        )

        self.assertEqual(self.inventory.quantity, 98)

        self.assertEqual(
            cancellation.admin_note,
            "Order is already being processed."
        )

    def test_duplicate_active_cancellation_request_is_rejected(self):

        order = self.create_order()
        admin_user = self.create_admin()

        OrderService.confirm_order(order.id, admin_user)

        OrderService.request_cancellation(
            user=self.user,
            order_id=order.id,
            reason="First request."
        )

        with self.assertRaises(ValidationError):

            OrderService.request_cancellation(
                user=self.user,
                order_id=order.id,
                reason="Second request."
            )

        self.assertEqual(
            OrderCancellation.objects.filter(
                order=order,
                status=OrderCancellation.CancellationStatus.REQUESTED
            ).count(),
            1
        )

    def test_cancelled_order_cannot_be_cancelled_again(self):

        order = self.create_order()

        OrderService.request_cancellation(
            user=self.user,
            order_id=order.id,
            reason="First cancellation."
        )

        with self.assertRaises(ValidationError):

            OrderService.request_cancellation(
                user=self.user,
                order_id=order.id,
                reason="Second cancellation."
            )

    def test_shipped_order_cannot_be_cancelled(self):

        order = self.create_order()

        order.status = Order.OrderStatus.SHIPPED
        order.save()

        with self.assertRaises(ValidationError):

            OrderService.request_cancellation(
                user=self.user,
                order_id=order.id,
                reason="Please cancel."
            )

    def test_customer_cannot_cancel_another_users_order(self):

        order = self.create_order()

        another_user = User.objects.create_user(
            username="another_customer",
            email="another@example.com",
            password="StrongPassword@123"
        )

        with self.assertRaises(ValidationError):

            OrderService.request_cancellation(
                user=another_user,
                order_id=order.id,
                reason="Cancel this order."
            )

    def test_rejected_cancellation_can_be_requested_again(self):

        order = self.create_order()
        admin_user = self.create_admin()

        OrderService.confirm_order(order.id, admin_user)

        first_cancellation = OrderService.request_cancellation(
            user=self.user,
            order_id=order.id,
            reason="First request."
        )

        OrderService.reject_cancellation(
            cancellation_id=first_cancellation.id,
            admin_user=admin_user
        )

        second_cancellation = OrderService.request_cancellation(
            user=self.user,
            order_id=order.id,
            reason="Second request."
        )

        self.assertEqual(
            second_cancellation.status,
            OrderCancellation.CancellationStatus.REQUESTED
        )
        
        # -----------------------------
    # Customer Cancellation API Tests
    # -----------------------------

    def test_customer_can_cancel_pending_order_through_api(self):

        order = self.create_order()

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            f"/api/v1/orders/{order.id}/cancel/",
            {
                "reason": "Ordered by mistake."
            },
            format="json"
        )

        order.refresh_from_db()

        self.assertEqual(response.status_code, 201)

        self.assertEqual(
            order.status,
            Order.OrderStatus.CANCELLED
        )

        self.assertEqual(
            response.data["cancellation"]["status"],
            OrderCancellation.CancellationStatus.DIRECT_CANCELLED
        )

        self.assertEqual(self.inventory.quantity, 100)

    def test_customer_can_request_cancellation_of_confirmed_order(self):

        order = self.create_order()
        admin_user = self.create_admin()

        OrderService.confirm_order(order.id, admin_user)

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            f"/api/v1/orders/{order.id}/cancel/",
            {
                "reason": "Customer changed their mind."
            },
            format="json"
        )

        order.refresh_from_db()

        self.assertEqual(response.status_code, 201)

        self.assertEqual(
            order.status,
            Order.OrderStatus.CONFIRMED
        )

        self.assertEqual(
            response.data["cancellation"]["status"],
            OrderCancellation.CancellationStatus.REQUESTED
        )

        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 98)

    def test_customer_cannot_cancel_another_users_order_through_api(self):

        order = self.create_order()

        another_user = User.objects.create_user(
            username="another_customer",
            email="another@example.com",
            password="StrongPassword@123"
        )

        self.client.force_authenticate(user=another_user)

        response = self.client.post(
            f"/api/v1/orders/{order.id}/cancel/",
            {
                "reason": "Cancel this order."
            },
            format="json"
        )

        self.assertIn(response.status_code, [400, 404])

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.PENDING
        )

    def test_customer_can_view_own_cancellation_history(self):

        order = self.create_order()

        OrderService.request_cancellation(
            user=self.user,
            order_id=order.id,
            reason="Ordered by mistake."
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/api/v1/orders/my-cancellations/"
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data["count"], 1)

        self.assertEqual(
            response.data["results"][0]["order"],
            order.id
        )

    def test_customer_cannot_view_another_users_cancellations(self):

        order = self.create_order()

        OrderService.request_cancellation(
            user=self.user,
            order_id=order.id,
            reason="Ordered by mistake."
        )

        another_user = User.objects.create_user(
            username="another_customer",
            email="another@example.com",
            password="StrongPassword@123"
        )

        self.client.force_authenticate(user=another_user)

        response = self.client.get(
            "/api/v1/orders/my-cancellations/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_unauthenticated_user_cannot_request_cancellation(self):

        order = self.create_order()

        response = APIClient().post(
            f"/api/v1/orders/{order.id}/cancel/",
            {
                "reason": "Please cancel."
            },
            format="json"
        )

        self.assertEqual(response.status_code, 401)

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.PENDING
        )

    def test_cancellation_api_rejects_empty_reason(self):

        order = self.create_order()

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            f"/api/v1/orders/{order.id}/cancel/",
            {
                "reason": ""
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)


    # -----------------------------
    # Admin Cancellation API Tests
    # -----------------------------

    def create_cancellation_request(self):

        order = self.create_order()
        admin_user = self.create_admin()

        OrderService.confirm_order(
            order_id=order.id,
            admin_user=admin_user
        )

        cancellation = OrderService.request_cancellation(
            user=self.user,
            order_id=order.id,
            reason="Customer requested cancellation."
        )

        return order, cancellation, admin_user

    def test_admin_can_list_cancellation_requests(self):

        order, cancellation, admin_user = (
            self.create_cancellation_request()
        )

        self.client.force_authenticate(user=admin_user)

        response = self.client.get(
            "/api/v1/orders/admin/cancellations/"
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data["count"], 1)

        self.assertEqual(
            response.data["results"][0]["id"],
            cancellation.id
        )

    def test_admin_can_filter_cancellation_requests_by_status(self):

        order, cancellation, admin_user = (
            self.create_cancellation_request()
        )

        self.client.force_authenticate(user=admin_user)

        response = self.client.get(
            "/api/v1/orders/admin/cancellations/?status=REQUESTED"
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data["count"], 1)

    def test_customer_cannot_access_admin_cancellation_list(self):

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/api/v1/orders/admin/cancellations/"
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_can_approve_cancellation_through_api(self):

        order, cancellation, admin_user = (
            self.create_cancellation_request()
        )

        self.client.force_authenticate(user=admin_user)

        response = self.client.post(
            f"/api/v1/orders/admin/cancellations/{cancellation.id}/approve/",
            {
                "admin_note": "Cancellation approved."
            },
            format="json"
        )

        order.refresh_from_db()
        cancellation.refresh_from_db()
        self.inventory.refresh_from_db()

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            order.status,
            Order.OrderStatus.CANCELLED
        )

        self.assertEqual(
            cancellation.status,
            OrderCancellation.CancellationStatus.APPROVED
        )

        self.assertEqual(self.inventory.quantity, 100)

        self.assertIsNotNone(order.stock_restored_at)
        
        
    def test_approve_cancellation_rejected_when_stock_was_never_deducted(self):

        order, cancellation, admin_user = (
            self.create_cancellation_request()
        )

        order.stock_deducted_at = None
        order.save(update_fields=["stock_deducted_at"])

        self.inventory.refresh_from_db()
        original_stock = self.inventory.quantity

        with self.assertRaises(ValidationError):
            OrderService.approve_cancellation(
                cancellation_id=cancellation.id,
                admin_user=admin_user,
            )

        order.refresh_from_db()
        cancellation.refresh_from_db()
        self.inventory.refresh_from_db()

        self.assertEqual(order.status, Order.OrderStatus.CONFIRMED)
        self.assertEqual(self.inventory.quantity, original_stock)

        self.assertEqual(
            cancellation.status,
            OrderCancellation.CancellationStatus.REQUESTED,
        )  
        
        
    def test_approve_cancellation_rejected_when_stock_already_restored(self):

        order, cancellation, admin_user = (
            self.create_cancellation_request()
        )

        order.refresh_from_db()

        # Simulate an already restored stock state.
        order.stock_restored_at = timezone.now()
        order.save(update_fields=["stock_restored_at"])

        self.inventory.refresh_from_db()
        original_stock = self.inventory.quantity

        with self.assertRaises(ValidationError):
            OrderService.approve_cancellation(
                cancellation_id=cancellation.id,
                admin_user=admin_user,
            )

        order.refresh_from_db()
        cancellation.refresh_from_db()
        self.inventory.refresh_from_db()

        self.assertEqual(order.status, Order.OrderStatus.CONFIRMED)

        self.assertEqual(
            self.inventory.quantity,
            original_stock,
        )

        self.assertEqual(
            cancellation.status,
            OrderCancellation.CancellationStatus.REQUESTED,
        )
    
      
    

    def test_admin_can_reject_cancellation_through_api(self):

        order, cancellation, admin_user = (
            self.create_cancellation_request()
        )

        self.client.force_authenticate(user=admin_user)

        response = self.client.post(
            f"/api/v1/orders/admin/cancellations/{cancellation.id}/reject/",
            {
                "admin_note": "Cancellation rejected."
            },
            format="json"
        )

        order.refresh_from_db()
        cancellation.refresh_from_db()
        self.inventory.refresh_from_db()

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            cancellation.status,
            OrderCancellation.CancellationStatus.REJECTED
        )

        self.assertEqual(
            order.status,
            Order.OrderStatus.CONFIRMED
        )

        self.assertEqual(self.inventory.quantity, 98)

    def test_customer_cannot_approve_cancellation(self):

        order, cancellation, admin_user = (
            self.create_cancellation_request()
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            f"/api/v1/orders/admin/cancellations/{cancellation.id}/approve/",
            {},
            format="json"
        )

        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_access_admin_cancellations(self):

        response = APIClient().get(
            "/api/v1/orders/admin/cancellations/"
        )

        self.assertEqual(response.status_code, 401)
        
    def test_confirmed_order_can_move_to_processing(self):
        order = self.create_order()
        admin = self.create_admin()

        OrderService.confirm_order(order.id, admin)

        updated_order = OrderService.update_order_status(
            order.id,
            Order.OrderStatus.PROCESSING,
            admin,
            note="Order processing started."
        )

        self.assertEqual(
            updated_order.status,
            Order.OrderStatus.PROCESSING
        )

        history = OrderStatusHistory.objects.filter(
            order=order
        ).latest("created_at")

        self.assertEqual(
            history.previous_status,
            Order.OrderStatus.CONFIRMED
        )
        self.assertEqual(
            history.new_status,
            Order.OrderStatus.PROCESSING
        )

    def test_processing_order_can_move_to_shipped(self):
        order = self.create_order()
        admin = self.create_admin()

        OrderService.confirm_order(order.id, admin)

        OrderService.update_order_status(
            order.id,
            Order.OrderStatus.PROCESSING,
            admin
        )

        updated_order = OrderService.update_order_status(
            order.id,
            Order.OrderStatus.SHIPPED,
            admin,
            note="Order handed over to delivery partner."
        )

        self.assertEqual(
            updated_order.status,
            Order.OrderStatus.SHIPPED
        )
        self.assertIsNotNone(updated_order.shipped_at)

        history = OrderStatusHistory.objects.filter(
            order=order
        ).latest("created_at")

        self.assertEqual(
            history.previous_status,
            Order.OrderStatus.PROCESSING
        )
        self.assertEqual(
            history.new_status,
            Order.OrderStatus.SHIPPED
        )

    def test_pending_order_cannot_move_directly_to_processing(self):
        order = self.create_order()
        admin = self.create_admin()

        with self.assertRaises(ValidationError):
            OrderService.update_order_status(
                order.id,
                Order.OrderStatus.PROCESSING,
                admin
            )

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.PENDING
        )

    def test_confirmed_order_cannot_move_directly_to_shipped(self):
        order = self.create_order()
        admin = self.create_admin()

        OrderService.confirm_order(order.id, admin)

        with self.assertRaises(ValidationError):
            OrderService.update_order_status(
                order.id,
                Order.OrderStatus.SHIPPED,
                admin
            )

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.CONFIRMED
        )

    def test_status_update_blocked_when_cancellation_is_pending(self):
        order = self.create_order()
        admin = self.create_admin()

        OrderService.confirm_order(order.id, admin)

        OrderService.request_cancellation(
            self.user,
            order.id,
            "Customer requested cancellation."
        )

        with self.assertRaises(ValidationError):
            OrderService.update_order_status(
                order.id,
                Order.OrderStatus.PROCESSING,
                admin
            )

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.CONFIRMED
        )

    def test_shipped_order_cannot_move_to_processing(self):
        order = self.create_order()
        admin = self.create_admin()

        OrderService.confirm_order(order.id, admin)

        OrderService.update_order_status(
            order.id,
            Order.OrderStatus.PROCESSING,
            admin
        )

        OrderService.update_order_status(
            order.id,
            Order.OrderStatus.SHIPPED,
            admin
        )

        with self.assertRaises(ValidationError):
            OrderService.update_order_status(
                order.id,
                Order.OrderStatus.PROCESSING,
                admin
            )

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.SHIPPED
        )
        
        # -----------------------------------------
    # Admin Order Status Update API Tests
    # -----------------------------------------

    def test_admin_can_update_confirmed_order_to_processing(self):

        order = self.create_order()
        admin = self.create_admin()

        OrderService.confirm_order(order.id, admin)

        self.client.force_authenticate(user=admin)

        response = self.client.post(
            f"/api/v1/orders/{order.id}/status/",
            {
                "status": "PROCESSING",
                "note": "Order processing started."
            },
            format="json"
        )

        order.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            order.status,
            Order.OrderStatus.PROCESSING
        )

        history = OrderStatusHistory.objects.filter(
            order=order
        ).latest("created_at")

        self.assertEqual(
            history.previous_status,
            Order.OrderStatus.CONFIRMED
        )
        self.assertEqual(
            history.new_status,
            Order.OrderStatus.PROCESSING
        )
        self.assertEqual(history.changed_by, admin)
        self.assertEqual(
            history.note,
            "Order processing started."
        )

    def test_admin_can_update_processing_order_to_shipped(self):

        order = self.create_order()
        admin = self.create_admin()

        OrderService.confirm_order(order.id, admin)

        OrderService.update_order_status(
            order.id,
            Order.OrderStatus.PROCESSING,
            admin
        )

        self.client.force_authenticate(user=admin)

        response = self.client.post(
            f"/api/v1/orders/{order.id}/status/",
            {
                "status": "SHIPPED",
                "note": "Order handed over to delivery partner."
            },
            format="json"
        )

        order.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            order.status,
            Order.OrderStatus.SHIPPED
        )
        self.assertIsNotNone(order.shipped_at)

        history = OrderStatusHistory.objects.filter(
            order=order
        ).latest("created_at")

        self.assertEqual(
            history.previous_status,
            Order.OrderStatus.PROCESSING
        )
        self.assertEqual(
            history.new_status,
            Order.OrderStatus.SHIPPED
        )
        self.assertEqual(history.changed_by, admin)

    def test_customer_cannot_update_order_status(self):

        order = self.create_order()

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            f"/api/v1/orders/{order.id}/status/",
            {
                "status": "PROCESSING"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 403)

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.PENDING
        )

    def test_unauthenticated_user_cannot_update_order_status(self):

        order = self.create_order()

        response = APIClient().post(
            f"/api/v1/orders/{order.id}/status/",
            {
                "status": "PROCESSING"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 401)

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.PENDING
        )

    def test_invalid_order_status_transition_is_rejected(self):

        order = self.create_order()
        admin = self.create_admin()

        self.client.force_authenticate(user=admin)

        response = self.client.post(
            f"/api/v1/orders/{order.id}/status/",
            {
                "status": "PROCESSING"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.PENDING
        )

    def test_status_update_blocked_when_cancellation_is_pending_api(self):

        order = self.create_order()
        admin = self.create_admin()

        OrderService.confirm_order(order.id, admin)

        OrderService.request_cancellation(
            self.user,
            order.id,
            "Customer requested cancellation."
        )

        self.client.force_authenticate(user=admin)

        response = self.client.post(
            f"/api/v1/orders/{order.id}/status/",
            {
                "status": "PROCESSING"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.CONFIRMED
        )

    def test_shipped_at_is_returned_in_status_update_response(self):

        order = self.create_order()
        admin = self.create_admin()

        OrderService.confirm_order(order.id, admin)

        OrderService.update_order_status(
            order.id,
            Order.OrderStatus.PROCESSING,
            admin
        )

        self.client.force_authenticate(user=admin)

        response = self.client.post(
            f"/api/v1/orders/{order.id}/status/",
            {
                "status": "SHIPPED"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["order"]["shipped_at"])

    def test_status_update_rejects_invalid_status_value(self):

        order = self.create_order()
        admin = self.create_admin()

        self.client.force_authenticate(user=admin)

        response = self.client.post(
            f"/api/v1/orders/{order.id}/status/",
            {
                "status": "DELIVERED"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)

        order.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.OrderStatus.PENDING
        )
        
        # -----------------------------------------
    # Customer Order Timeline API Tests
    # -----------------------------------------

    def test_customer_can_view_own_order_timeline(self):

        order = self.create_order()

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/orders/{order.id}/timeline/"
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["new_status"],
            Order.OrderStatus.PENDING
        )

    def test_order_timeline_is_returned_chronologically(self):

        order = self.create_order()
        admin = self.create_admin()

        OrderService.confirm_order(order.id, admin)

        OrderService.update_order_status(
            order.id,
            Order.OrderStatus.PROCESSING,
            admin
        )

        OrderService.update_order_status(
            order.id,
            Order.OrderStatus.SHIPPED,
            admin
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/orders/{order.id}/timeline/"
        )

        self.assertEqual(response.status_code, 200)

        statuses = [
            item["new_status"]
            for item in response.data["results"]
        ]

        self.assertEqual(
            statuses,
            [
                "PENDING",
                "CONFIRMED",
                "PROCESSING",
                "SHIPPED"
            ]
        )

    def test_customer_cannot_view_another_users_order_timeline(self):

        order = self.create_order()

        another_user = User.objects.create_user(
            username="another_customer",
            email="another@example.com",
            password="StrongPassword@123"
        )

        self.client.force_authenticate(user=another_user)

        response = self.client.get(
            f"/api/v1/orders/{order.id}/timeline/"
        )

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_user_cannot_view_order_timeline(self):

        order = self.create_order()

        response = APIClient().get(
            f"/api/v1/orders/{order.id}/timeline/"
        )

        self.assertEqual(response.status_code, 401)

    def test_empty_order_timeline_returns_empty_list(self):

        order = self.create_order()

        # Remove existing initial PENDING history.
        OrderStatusHistory.objects.filter(
            order=order
        ).delete()

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/orders/{order.id}/timeline/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])
        
        # -----------------------------------------
    # Admin Order Management API Tests
    # -----------------------------------------

    def create_additional_order(self):
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            purchase_mode="RETAIL",
            quantity=2,
        )
        return self.create_order()

    def test_admin_can_list_all_orders(self):
        order1 = self.create_order()
        order2 = self.create_additional_order()

        admin = self.create_admin()
        self.client.force_authenticate(user=admin)

        response = self.client.get("/api/v1/orders/admin/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

        order_ids = [
            item["id"] for item in response.data["results"]
        ]

        self.assertIn(order1.id, order_ids)
        self.assertIn(order2.id, order_ids)

    def test_customer_cannot_access_admin_order_list(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/orders/admin/")

        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_access_admin_order_list(self):
        response = APIClient().get("/api/v1/orders/admin/")

        self.assertEqual(response.status_code, 401)

    def test_admin_can_search_orders_by_order_number(self):
        order = self.create_order()
        admin = self.create_admin()

        self.client.force_authenticate(user=admin)

        response = self.client.get(
            f"/api/v1/orders/admin/?search={order.order_number}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            order.id,
        )

    def test_admin_can_search_orders_by_customer_details(self):
        order = self.create_order()
        admin = self.create_admin()

        self.client.force_authenticate(user=admin)

        for search_term in [
            "Test Customer",
            "customer@example.com",
        ]:
            response = self.client.get(
                f"/api/v1/orders/admin/?search={search_term}"
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 1)
            self.assertEqual(
                response.data["results"][0]["id"],
                order.id,
            )

    def test_admin_can_filter_orders_by_status(self):
        order1 = self.create_order()
        order2 = self.create_additional_order()

        order2.status = Order.OrderStatus.CONFIRMED
        order2.save()

        admin = self.create_admin()
        self.client.force_authenticate(user=admin)

        response = self.client.get(
            "/api/v1/orders/admin/?status=CONFIRMED"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            order2.id,
        )

    def test_admin_can_filter_orders_by_payment_status(self):
        order1 = self.create_order()
        order2 = self.create_additional_order()

        order2.payment_status = Order.PaymentStatus.PAID
        order2.save()

        admin = self.create_admin()
        self.client.force_authenticate(user=admin)

        response = self.client.get(
            "/api/v1/orders/admin/?payment_status=PAID"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            order2.id,
        )

    def test_admin_order_list_rejects_invalid_filters(self):
        admin = self.create_admin()
        self.client.force_authenticate(user=admin)

        invalid_urls = [
            "/api/v1/orders/admin/?status=INVALID",
            "/api/v1/orders/admin/?payment_status=INVALID",
        ]

        for url in invalid_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 400)

    def test_admin_order_list_supports_pagination(self):
        self.create_order()
        self.create_additional_order()
        self.create_additional_order()

        admin = self.create_admin()
        self.client.force_authenticate(user=admin)

        response = self.client.get(
            "/api/v1/orders/admin/?page_size=2"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 2)

    def test_admin_can_view_order_detail_with_customer_information(self):
        order = self.create_order()

        admin = self.create_admin()
        self.client.force_authenticate(user=admin)

        response = self.client.get(
            f"/api/v1/orders/admin/{order.id}/"
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["customer_email"],
            "customer@example.com",
        )

        self.assertEqual(
            response.data["customer_name"],
            "Test Customer",
        )

        self.assertEqual(len(response.data["items"]), 1)

    def test_admin_order_detail_returns_404_for_nonexistent_order(self):
        admin = self.create_admin()
        self.client.force_authenticate(user=admin)

        response = self.client.get(
            "/api/v1/orders/admin/999999/"
        )

        self.assertEqual(response.status_code, 404)


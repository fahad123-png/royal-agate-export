from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile
from apps.orders.models import Order
from apps.payments.models import Payment, Refund
from apps.payments.services import RefundService


User = get_user_model()


class CustomerDashboardOverviewTests(TestCase):

    def setUp(self):
        self.customer = User.objects.create_user(
            username="dashboard_customer",
            email="dashboard@example.com",
            password="StrongPassword@123",
            first_name="Test",
            last_name="Customer",
        )

        CustomerProfile.objects.create(
            user=self.customer,
            phone_number="9876543210",
        )

        self.admin = User.objects.create_superuser(
            username="dashboard_admin",
            email="admin_dashboard@example.com",
            password="StrongPassword@123",
        )

        self.client = APIClient()

        self.url = "/api/v1/dashboard/customer/overview/"

    def create_order(self, status, order_number):
        return Order.objects.create(
            order_number=order_number,
            user=self.customer,
            shipping_full_name="Test Customer",
            shipping_phone_number="9876543210",
            shipping_address_line_1="Test Address",
            shipping_city="Surat",
            shipping_state="Gujarat",
            shipping_pincode="395007",
            subtotal=Decimal("1000.00"),
            shipping_charge=Decimal("0.00"),
            discount=Decimal("0.00"),
            total_amount=Decimal("1000.00"),
            status=status,
            payment_status=Order.PaymentStatus.PENDING,
        )

    def test_customer_can_view_dashboard(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertIn("customer", response.data)
        self.assertIn("statistics", response.data)
        self.assertIn("recent_orders", response.data)

    def test_unauthenticated_user_cannot_view_dashboard(self):
        response = APIClient().get(self.url)

        self.assertEqual(response.status_code, 401)

    def test_admin_cannot_access_customer_dashboard(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_dashboard_shows_only_own_orders(self):
        self.create_order(
            Order.OrderStatus.PENDING,
            "DASH-001",
        )

        another_customer = User.objects.create_user(
            username="another_customer",
            email="another@example.com",
            password="StrongPassword@123",
        )

        Order.objects.create(
            order_number="DASH-002",
            user=another_customer,
            shipping_full_name="Another Customer",
            shipping_phone_number="9876543211",
            shipping_address_line_1="Another Address",
            shipping_city="Ahmedabad",
            shipping_state="Gujarat",
            shipping_pincode="380001",
            subtotal=Decimal("2000.00"),
            shipping_charge=Decimal("0.00"),
            discount=Decimal("0.00"),
            total_amount=Decimal("2000.00"),
            status=Order.OrderStatus.CONFIRMED,
        )

        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["statistics"]["total_orders"],
            1,
        )

    def test_recent_orders_are_limited_to_five(self):
        for i in range(6):
            self.create_order(
                Order.OrderStatus.PENDING,
                f"DASH-RECENT-{i}",
            )

        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(response.data["recent_orders"]), 5)

    def test_total_spent_excludes_pending_payments(self):
        order = self.create_order(
            Order.OrderStatus.PENDING,
            "DASH-PAY-001",
        )

        Payment.objects.create(
            order=order,
            payment_method=Payment.PaymentMethod.RAZORPAY,
            status=Payment.PaymentStatus.PENDING,
            amount=Decimal("1000.00"),
        )

        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["statistics"]["total_spent"],
            "0.00",
        )

    def test_total_spent_deducts_completed_refunds(self):
        order = self.create_order(
            Order.OrderStatus.CANCELLED,
            "DASH-REFUND-001",
        )

        payment = Payment.objects.create(
            order=order,
            payment_method=Payment.PaymentMethod.RAZORPAY,
            status=Payment.PaymentStatus.SUCCESS,
            amount=Decimal("1000.00"),
        )

        refund = RefundService.create_refund(
            payment_id=payment.id,
            amount=Decimal("250.00"),
            refund_method=Refund.RefundMethod.UPI,
            admin_user=self.admin,
        )

        RefundService.start_refund(
            refund_id=refund.id,
            admin_user=self.admin,
        )

        RefundService.complete_refund(
            refund_id=refund.id,
            transaction_reference="UPI-REF-TEST-001",
            admin_user=self.admin,
        )

        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["statistics"]["total_spent"],
            "750.00",
        )
        
class CustomerRefundListTests(TestCase):

    def setUp(self):
        self.customer = User.objects.create_user(
            username="refund_customer",
            email="refund@example.com",
            password="StrongPassword@123",
            first_name="Refund",
            last_name="Customer",
        )

        CustomerProfile.objects.create(
            user=self.customer,
            phone_number="9876543210",
        )

        self.admin = User.objects.create_superuser(
            username="refund_admin",
            email="refund_admin@example.com",
            password="StrongPassword@123",
        )

        self.client = APIClient()

        self.url = "/api/v1/dashboard/customer/refunds/"

    def create_refund(self, user, order_number):
        order = Order.objects.create(
            order_number=order_number,
            user=user,
            shipping_full_name="Test Customer",
            shipping_phone_number="9876543210",
            shipping_address_line_1="Test Address",
            shipping_city="Surat",
            shipping_state="Gujarat",
            shipping_pincode="395007",
            subtotal=Decimal("1000.00"),
            shipping_charge=Decimal("0.00"),
            discount=Decimal("0.00"),
            total_amount=Decimal("1000.00"),
            status=Order.OrderStatus.CANCELLED,
            payment_status=Order.PaymentStatus.PAID,
        )

        payment = Payment.objects.create(
            order=order,
            payment_method=Payment.PaymentMethod.RAZORPAY,
            status=Payment.PaymentStatus.SUCCESS,
            amount=Decimal("1000.00"),
        )

        refund = RefundService.create_refund(
            payment_id=payment.id,
            amount=Decimal("250.00"),
            refund_method=Refund.RefundMethod.UPI,
            admin_user=self.admin,
            admin_note="Internal admin note",
        )

        return refund

    def test_customer_can_view_own_refunds(self):
        refund = self.create_refund(
            self.customer,
            "REFUND-001",
        )

        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        self.assertEqual(
            response.data[0]["id"],
            refund.id,
        )

        self.assertEqual(
            response.data[0]["order_number"],
            "REFUND-001",
        )

    def test_customer_cannot_see_other_customers_refunds(self):
        another_customer = User.objects.create_user(
            username="other_refund_customer",
            email="other_refund@example.com",
            password="StrongPassword@123",
        )

        self.create_refund(
            self.customer,
            "REFUND-OWN",
        )

        self.create_refund(
            another_customer,
            "REFUND-OTHER",
        )

        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        self.assertEqual(
            response.data[0]["order_number"],
            "REFUND-OWN",
        )

    def test_refund_response_does_not_expose_admin_fields(self):
        self.create_refund(
            self.customer,
            "REFUND-SAFE",
        )

        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        refund_data = response.data[0]

        self.assertNotIn("admin_note", refund_data)
        self.assertNotIn("processed_by", refund_data)

    def test_unauthenticated_user_cannot_view_refunds(self):
        response = APIClient().get(self.url)

        self.assertEqual(response.status_code, 401)

    def test_admin_cannot_access_customer_refund_list(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_customer_gets_empty_list_when_no_refunds_exist(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        
class AdminDashboardOverviewTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin_overview",
            email="admin_overview@example.com",
            password="StrongPassword@123",
        )

        self.customer = User.objects.create_user(
            username="customer_overview",
            email="customer_overview@example.com",
            password="StrongPassword@123",
        )

        self.client = APIClient()
        self.url = "/api/v1/dashboard/admin/overview/"

    def test_admin_can_view_dashboard(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertIn("sales", response.data)
        self.assertIn("orders", response.data)
        self.assertIn("products", response.data)
        self.assertIn("inventory", response.data)
        self.assertIn("payments", response.data)
        self.assertIn("refunds", response.data)

    def test_customer_cannot_access_admin_dashboard(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_access_admin_dashboard(self):
        response = APIClient().get(self.url)

        self.assertEqual(response.status_code, 401)
        
    def create_order(self):
        return Order.objects.create(
            order_number="ADMIN-DASH-001",
            user=self.customer,
            shipping_full_name="Test Customer",
            shipping_phone_number="9876543210",
            shipping_address_line_1="Test Address",
            shipping_city="Surat",
            shipping_state="Gujarat",
            shipping_pincode="395007",
            subtotal=Decimal("1000.00"),
            shipping_charge=Decimal("0.00"),
            discount=Decimal("0.00"),
            total_amount=Decimal("1000.00"),
            status=Order.OrderStatus.CANCELLED,
            payment_status=Order.PaymentStatus.PAID,
        )


    def test_dashboard_calculates_revenue_and_refunds_correctly(self):
        order = self.create_order()

        successful_payment = Payment.objects.create(
            order=order,
            payment_method=Payment.PaymentMethod.RAZORPAY,
            status=Payment.PaymentStatus.SUCCESS,
            amount=Decimal("1000.00"),
        )

        Payment.objects.create(
            order=order,
            payment_method=Payment.PaymentMethod.RAZORPAY,
            status=Payment.PaymentStatus.PENDING,
            amount=Decimal("300.00"),
        )

        Payment.objects.create(
            order=order,
            payment_method=Payment.PaymentMethod.RAZORPAY,
            status=Payment.PaymentStatus.FAILED,
            amount=Decimal("400.00"),
        )

        refund = RefundService.create_refund(
            payment_id=successful_payment.id,
            amount=Decimal("250.00"),
            refund_method=Refund.RefundMethod.UPI,
            admin_user=self.admin,
        )

        RefundService.start_refund(
            refund_id=refund.id,
            admin_user=self.admin,
        )

        RefundService.complete_refund(
            refund_id=refund.id,
            transaction_reference="ADMIN-REF-001",
            admin_user=self.admin,
        )

        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["sales"]["total_revenue"],
            "1000.00",
        )

        self.assertEqual(
            response.data["sales"]["total_refunded"],
            "250.00",
        )

        self.assertEqual(
            response.data["sales"]["net_revenue"],
            "750.00",
        )

        self.assertEqual(
            response.data["payments"]["successful_payments"],
            1,
        )

        self.assertEqual(
            response.data["payments"]["pending_payments"],
            1,
        )

        self.assertEqual(
            response.data["payments"]["failed_payments"],
            1,
        )
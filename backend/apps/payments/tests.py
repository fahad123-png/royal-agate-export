from decimal import Decimal

from rest_framework.test import APIClient

from django.contrib.auth import get_user_model
from django.test import TestCase

from rest_framework.exceptions import ValidationError

from apps.orders.models import Order
from apps.payments.models import Payment, Refund
from apps.payments.services import RefundService


User = get_user_model()


class RefundServiceTests(TestCase):

    def setUp(self):
        self.customer = User.objects.create_user(
            username="customer",
            email="customer@example.com",
            password="TestPassword123!",
        )

        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="AdminPassword123!",
        )

        self.order = Order.objects.create(
            order_number="ORD-REFUND-001",
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

        self.payment = Payment.objects.create(
            order=self.order,
            payment_method=Payment.PaymentMethod.RAZORPAY,
            status=Payment.PaymentStatus.SUCCESS,
            amount=Decimal("1000.00"),
            transaction_id="PAY-TEST-001",
        )

    def create_refund(self, amount="100.00"):
        return RefundService.create_refund(
            payment_id=self.payment.id,
            amount=Decimal(amount),
            refund_method=Refund.RefundMethod.UPI,
            admin_user=self.admin,
        )

    # --------------------------------------------------
    # REFUND CREATION TESTS
    # --------------------------------------------------

    def test_create_refund_successfully(self):
        refund = self.create_refund("200.00")

        self.assertEqual(refund.amount, Decimal("200.00"))
        self.assertEqual(refund.status, Refund.RefundStatus.PENDING)
        self.assertEqual(refund.payment, self.payment)

    def test_refund_rejected_for_non_cancelled_order(self):
        self.order.status = Order.OrderStatus.PENDING
        self.order.save()

        with self.assertRaises(ValidationError):
            self.create_refund()

    def test_refund_rejected_for_failed_payment(self):
        self.payment.status = Payment.PaymentStatus.FAILED
        self.payment.save()

        with self.assertRaises(ValidationError):
            self.create_refund()

    def test_partial_refunds_are_allowed(self):
        refund1 = self.create_refund("400.00")
        refund2 = self.create_refund("300.00")

        self.assertEqual(refund1.amount, Decimal("400.00"))
        self.assertEqual(refund2.amount, Decimal("300.00"))

    def test_full_refund_is_allowed(self):
        refund = self.create_refund("1000.00")

        self.assertEqual(refund.amount, Decimal("1000.00"))

    def test_over_refunding_is_rejected(self):
        self.create_refund("700.00")

        with self.assertRaises(ValidationError):
            self.create_refund("400.00")

    def test_pending_refund_amount_is_reserved(self):
        self.create_refund("600.00")

        with self.assertRaises(ValidationError):
            self.create_refund("500.00")

    def test_failed_refund_amount_becomes_available_again(self):
        refund = self.create_refund("600.00")

        RefundService.fail_refund(
            refund_id=refund.id,
            admin_user=self.admin,
        )

        new_refund = self.create_refund("600.00")

        self.assertEqual(
            new_refund.amount,
            Decimal("600.00"),
        )

    def test_zero_refund_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.create_refund("0.00")

    def test_invalid_refund_method_is_rejected(self):
        with self.assertRaises(ValidationError):
            RefundService.create_refund(
                payment_id=self.payment.id,
                amount=Decimal("100.00"),
                refund_method="INVALID",
                admin_user=self.admin,
            )

    # --------------------------------------------------
    # REFUND PROCESSING TESTS
    # --------------------------------------------------

    def test_start_refund_successfully(self):
        refund = self.create_refund()

        updated_refund = RefundService.start_refund(
            refund_id=refund.id,
            admin_user=self.admin,
        )

        self.assertEqual(
            updated_refund.status,
            Refund.RefundStatus.PROCESSING,
        )

    def test_only_pending_refund_can_be_started(self):
        refund = self.create_refund()

        RefundService.start_refund(
            refund_id=refund.id,
            admin_user=self.admin,
        )

        with self.assertRaises(ValidationError):
            RefundService.start_refund(
                refund_id=refund.id,
                admin_user=self.admin,
            )

    def test_complete_refund_successfully(self):
        refund = self.create_refund()

        RefundService.start_refund(
            refund_id=refund.id,
            admin_user=self.admin,
        )

        completed_refund = RefundService.complete_refund(
            refund_id=refund.id,
            transaction_reference="UPI-REF-123456",
            admin_user=self.admin,
        )

        self.assertEqual(
            completed_refund.status,
            Refund.RefundStatus.COMPLETED,
        )

        self.assertEqual(
            completed_refund.transaction_reference,
            "UPI-REF-123456",
        )

        self.assertIsNotNone(completed_refund.completed_at)

    def test_completion_requires_transaction_reference(self):
        refund = self.create_refund()

        RefundService.start_refund(
            refund_id=refund.id,
            admin_user=self.admin,
        )

        with self.assertRaises(ValidationError):
            RefundService.complete_refund(
                refund_id=refund.id,
                transaction_reference="   ",
                admin_user=self.admin,
            )

    def test_completed_refund_cannot_be_completed_again(self):
        refund = self.create_refund()

        RefundService.start_refund(
            refund_id=refund.id,
            admin_user=self.admin,
        )

        RefundService.complete_refund(
            refund_id=refund.id,
            transaction_reference="UPI-REF-123",
            admin_user=self.admin,
        )

        with self.assertRaises(ValidationError):
            RefundService.complete_refund(
                refund_id=refund.id,
                transaction_reference="UPI-REF-456",
                admin_user=self.admin,
            )

    def test_fail_refund_successfully(self):
        refund = self.create_refund()

        failed_refund = RefundService.fail_refund(
            refund_id=refund.id,
            admin_user=self.admin,
            admin_note="Bank transaction failed.",
        )

        self.assertEqual(
            failed_refund.status,
            Refund.RefundStatus.FAILED,
        )

        self.assertEqual(
            failed_refund.admin_note,
            "Bank transaction failed.",
        )

    def test_completed_refund_cannot_be_failed(self):
        refund = self.create_refund()

        RefundService.start_refund(
            refund_id=refund.id,
            admin_user=self.admin,
        )

        RefundService.complete_refund(
            refund_id=refund.id,
            transaction_reference="UPI-REF-123",
            admin_user=self.admin,
        )

        with self.assertRaises(ValidationError):
            RefundService.fail_refund(
                refund_id=refund.id,
                admin_user=self.admin,
            )

    def test_original_payment_status_remains_success(self):
        refund = self.create_refund()

        RefundService.start_refund(
            refund_id=refund.id,
            admin_user=self.admin,
        )

        RefundService.complete_refund(
            refund_id=refund.id,
            transaction_reference="UPI-REF-123",
            admin_user=self.admin,
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            Payment.PaymentStatus.SUCCESS,
        )
        
class RefundAPITests(TestCase):

    def setUp(self):
        self.customer = User.objects.create_user(
            username="api_customer",
            email="api_customer@example.com",
            password="TestPassword123!",
        )

        self.admin = User.objects.create_superuser(
            username="api_admin",
            email="api_admin@example.com",
            password="AdminPassword123!",
        )

        self.order = Order.objects.create(
            order_number="ORD-API-001",
            user=self.customer,
            shipping_full_name="API Customer",
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

        self.payment = Payment.objects.create(
            order=self.order,
            payment_method=Payment.PaymentMethod.RAZORPAY,
            status=Payment.PaymentStatus.SUCCESS,
            amount=Decimal("1000.00"),
            transaction_id="API-PAY-001",
        )

        self.client = APIClient()

        self.refunds_url = "/api/v1/payments/refunds/"

    def authenticate_admin(self):
        self.client.force_authenticate(user=self.admin)

    def authenticate_customer(self):
        self.client.force_authenticate(user=self.customer)

    def create_refund(self):
        return RefundService.create_refund(
            payment_id=self.payment.id,
            amount=Decimal("200.00"),
            refund_method=Refund.RefundMethod.UPI,
            admin_user=self.admin,
        )

    # ------------------------------------------
    # ACCESS CONTROL TESTS
    # ------------------------------------------

    def test_unauthenticated_user_cannot_list_refunds(self):
        response = self.client.get(self.refunds_url)

        self.assertEqual(response.status_code, 401)

    def test_customer_cannot_list_refunds(self):
        self.authenticate_customer()

        response = self.client.get(self.refunds_url)

        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_create_refund(self):
        self.authenticate_customer()

        response = self.client.post(
            self.refunds_url,
            {
                "payment_id": self.payment.id,
                "amount": "200.00",
                "refund_method": "UPI",
            },
        )

        self.assertEqual(response.status_code, 403)

    # ------------------------------------------
    # REFUND CREATION AND LIST TESTS
    # ------------------------------------------

    def test_admin_can_create_refund(self):
        self.authenticate_admin()

        response = self.client.post(
            self.refunds_url,
            {
                "payment_id": self.payment.id,
                "amount": "200.00",
                "refund_method": "UPI",
                "admin_note": "Customer order cancelled.",
            },
        )

        self.assertEqual(response.status_code, 201)

        self.assertEqual(
            response.data["refund"]["status"],
            Refund.RefundStatus.PENDING,
        )

    def test_admin_can_list_refunds(self):
        self.authenticate_admin()

        self.create_refund()

        response = self.client.get(self.refunds_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_invalid_refund_data_is_rejected(self):
        self.authenticate_admin()

        response = self.client.post(
            self.refunds_url,
            {
                "payment_id": self.payment.id,
                "amount": "0.00",
                "refund_method": "UPI",
            },
        )

        self.assertEqual(response.status_code, 400)

    # ------------------------------------------
    # REFUND PROCESSING API TESTS
    # ------------------------------------------

    def test_admin_can_start_refund_processing(self):
        self.authenticate_admin()

        refund = self.create_refund()

        response = self.client.post(
            f"{self.refunds_url}{refund.id}/process/"
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["refund"]["status"],
            Refund.RefundStatus.PROCESSING,
        )

    def test_admin_can_complete_refund(self):
        self.authenticate_admin()

        refund = self.create_refund()

        self.client.post(
            f"{self.refunds_url}{refund.id}/process/"
        )

        response = self.client.post(
            f"{self.refunds_url}{refund.id}/complete/",
            {
                "transaction_reference": "UPI-API-12345",
                "admin_note": "Refund transferred successfully.",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["refund"]["status"],
            Refund.RefundStatus.COMPLETED,
        )

        self.assertEqual(
            response.data["refund"]["transaction_reference"],
            "UPI-API-12345",
        )

    def test_admin_can_mark_refund_failed(self):
        self.authenticate_admin()

        refund = self.create_refund()

        response = self.client.post(
            f"{self.refunds_url}{refund.id}/fail/",
            {
                "admin_note": "Bank transfer failed.",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["refund"]["status"],
            Refund.RefundStatus.FAILED,
        )

    def test_refund_completion_requires_transaction_reference(self):
        self.authenticate_admin()

        refund = self.create_refund()

        self.client.post(
            f"{self.refunds_url}{refund.id}/process/"
        )

        response = self.client.post(
            f"{self.refunds_url}{refund.id}/complete/",
            {
                "transaction_reference": "   ",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_customer_cannot_process_refund(self):
        refund = self.create_refund()

        self.authenticate_customer()

        response = self.client.post(
            f"{self.refunds_url}{refund.id}/process/"
        )

        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_complete_refund(self):
        refund = self.create_refund()

        self.authenticate_customer()

        response = self.client.post(
            f"{self.refunds_url}{refund.id}/complete/",
            {
                "transaction_reference": "UPI-12345",
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_fail_refund(self):
        refund = self.create_refund()

        self.authenticate_customer()

        response = self.client.post(
            f"{self.refunds_url}{refund.id}/fail/",
            {
                "admin_note": "Failed",
            },
        )

        self.assertEqual(response.status_code, 403)
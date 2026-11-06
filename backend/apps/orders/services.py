import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from rest_framework.exceptions import ValidationError

from apps.cart.services import CartService
from apps.orders.models import (
    Order,
    OrderItem,
    OrderCancellation,
    OrderStatusHistory,
)
from apps.payments.models import Payment
from apps.inventory.services import InventoryService
from apps.catalogue.models import Product


class OrderService:

    @staticmethod
    def record_status_history(
        order,
        previous_status,
        new_status,
        changed_by=None,
        note="",
    ):
        """Create an audit entry for an order status change."""
        return OrderStatusHistory.objects.create(
            order=order,
            previous_status=previous_status,
            new_status=new_status,
            changed_by=changed_by,
            note=note,
        )

    @staticmethod
    @transaction.atomic
    def create_order(user, address_id, notes=""):
        # 1. Validate checkout.
        checkout_data = CartService.validate_checkout(
            user=user,
            address_id=address_id,
        )

        cart = checkout_data["cart"]
        address = checkout_data["address"]

        # 2. Generate a unique order number.
        order_number = (
            f"RA-{timezone.now():%Y%m%d}-"
            f"{uuid.uuid4().hex[:12].upper()}"
        )

        # 3. Create order with a shipping-address snapshot.
        order = Order.objects.create(
            order_number=order_number,
            user=user,
            shipping_full_name=address.full_name,
            shipping_phone_number=address.phone_number,
            shipping_address_line_1=address.address_line_1,
            shipping_address_line_2=address.address_line_2,
            shipping_city=address.city,
            shipping_state=address.state,
            shipping_pincode=address.pincode,
            shipping_country=address.country,
            subtotal=checkout_data["subtotal"],
            shipping_charge=Decimal("0.00"),
            discount=Decimal("0.00"),
            total_amount=checkout_data["total_amount"],
            status=Order.OrderStatus.PENDING,
            payment_status=Order.PaymentStatus.PENDING,
            notes=notes,
        )

        # 4. Record the initial order status.
        OrderService.record_status_history(
            order=order,
            previous_status="",
            new_status=Order.OrderStatus.PENDING,
            changed_by=user,
            note="Order placed successfully.",
        )

        # 5. Create order items with purchase-time snapshots.
        order_items = []

        for item_data in checkout_data["items"]:
            cart_item = item_data["cart_item"]

            order_items.append(
                OrderItem(
                    order=order,
                    product=cart_item.product,
                    product_name=cart_item.product.name,
                    product_sku=cart_item.product.sku,
                    purchase_mode=cart_item.purchase_mode,
                    quantity=cart_item.quantity,
                    unit_price=item_data["unit_price"],
                    subtotal=item_data["subtotal"],
                )
            )

        OrderItem.objects.bulk_create(order_items)

        # 6. Create the initial payment record.
        Payment.objects.create(
            order=order,
            amount=order.total_amount,
            status=Payment.PaymentStatus.PENDING,
        )

        # 7. Clear the cart only after successful order creation.
        cart.items.all().delete()

        return order

    @staticmethod
    @transaction.atomic
    def confirm_order(order_id, admin_user):

        # 1. Lock the order row.
        try:
            order = Order.objects.select_for_update().get(
                pk=order_id
            )
        except Order.DoesNotExist:
            raise ValidationError("Order does not exist.")

        # 2. Validate order status.
        if order.status != Order.OrderStatus.PENDING:
            raise ValidationError(
                "Only pending orders can be confirmed."
            )

        # 3. Prevent duplicate stock deduction.
        if order.stock_deducted_at is not None:
            raise ValidationError(
                "Stock has already been deducted for this order."
            )

        # 4. Retrieve order items in consistent product order.
        order_items = list(
            OrderItem.objects.filter(
                order=order
            ).order_by("product_id", "pk")
        )

        if not order_items:
            raise ValidationError(
                "Cannot confirm an order without items."
            )

        # 5. Collect product IDs.
        product_ids = sorted({
            item.product_id
            for item in order_items
            if item.product_id is not None
        })

        # 6. Lock all products in ascending ID order.
        products = Product.objects.select_for_update().filter(
            id__in=product_ids
        ).order_by("id")

        product_map = {
            product.id: product
            for product in products
        }

        previous_status = order.status

        # 7. Deduct stock in consistent product order.
        for item in order_items:

            product = product_map.get(item.product_id)

            if product is None:
                raise ValidationError(
                    f"Product for order item '{item.product_name}' "
                    "no longer exists."
                )

            InventoryService.decrease_stock(
                product=product,
                quantity=item.quantity,
                reason=f"Stock deducted for order {order.order_number}",
                created_by=admin_user,
            )

        # 8. Update order status and stock-deduction timestamp.
        order.status = Order.OrderStatus.CONFIRMED
        order.stock_deducted_at = timezone.now()

        order.save(
            update_fields=[
                "status",
                "stock_deducted_at",
                "updated_at"
            ]
        )

        # 9. Record status history.
        OrderService.record_status_history(
            order=order,
            previous_status=previous_status,
            new_status=order.status,
            changed_by=admin_user,
            note="Order confirmed by admin.",
        )

        return order

    @staticmethod
    @transaction.atomic
    def request_cancellation(user, order_id, reason):
        # 1. Lock the customer's order.
        try:
            order = Order.objects.select_for_update().get(
                pk=order_id,
                user=user,
            )
        except Order.DoesNotExist:
            raise ValidationError("Order does not exist.")

        # 2. Validate the cancellation reason.
        reason = reason.strip()
        if not reason:
            raise ValidationError(
                {"reason": "Cancellation reason is required."}
            )

        previous_status = order.status

        # 3. Determine whether cancellation is direct or requires approval.
        if order.status == Order.OrderStatus.PENDING:
            cancellation_status = (
                OrderCancellation.CancellationStatus.DIRECT_CANCELLED
            )
            order.status = Order.OrderStatus.CANCELLED

        elif order.status in [
            Order.OrderStatus.CONFIRMED,
            Order.OrderStatus.PROCESSING,
        ]:
            cancellation_status = (
                OrderCancellation.CancellationStatus.REQUESTED
            )

            active_request_exists = OrderCancellation.objects.filter(
                order=order,
                status=OrderCancellation.CancellationStatus.REQUESTED,
            ).exists()

            if active_request_exists:
                raise ValidationError(
                    "A cancellation request already exists."
                )

        else:
            raise ValidationError("This order cannot be cancelled.")

        # 4. Create the cancellation record.
        cancellation = OrderCancellation.objects.create(
            order=order,
            requested_by=user,
            reason=reason,
            status=cancellation_status,
        )

        # 5. Save and record direct cancellation only.
        if order.status == Order.OrderStatus.CANCELLED:
            order.save(update_fields=["status", "updated_at"])

            OrderService.record_status_history(
                order=order,
                previous_status=previous_status,
                new_status=order.status,
                changed_by=user,
                note=f"Order cancelled. Reason: {reason}",
            )

        return cancellation

    @staticmethod
    @transaction.atomic
    def approve_cancellation(cancellation_id, admin_user, admin_note=""):
        # Read the order ID first, then lock Order before OrderCancellation.
        # This keeps lock ordering consistent with request_cancellation().
        try:
            cancellation_order_id = (
                OrderCancellation.objects
                .only("order_id")
                .get(pk=cancellation_id)
                .order_id
            )
        except OrderCancellation.DoesNotExist:
            raise ValidationError(
                "Cancellation request does not exist."
            )

        # 1. Lock the order row first.
        try:
            order = Order.objects.select_for_update().get(
                pk=cancellation_order_id
            )
        except Order.DoesNotExist:
            raise ValidationError("Order does not exist.")

        # 2. Lock and re-fetch the cancellation record.
        try:
            cancellation = (
                OrderCancellation.objects
                .select_for_update()
                .get(pk=cancellation_id, order=order)
            )
        except OrderCancellation.DoesNotExist:
            raise ValidationError(
                "Cancellation request does not exist."
            )

        # 3. Validate cancellation request and current order status.
        if cancellation.status != (
            OrderCancellation.CancellationStatus.REQUESTED
        ):
            raise ValidationError(
                "This cancellation request has already been processed."
            )

        if order.status not in [
            Order.OrderStatus.CONFIRMED,
            Order.OrderStatus.PROCESSING,
        ]:
            raise ValidationError("This order cannot be cancelled.")

        previous_status = order.status

        # 4. Validate stock deduction state before restoring stock.
        if order.stock_deducted_at is None:
            raise ValidationError(
                "Cannot approve cancellation because stock "
                "was never recorded as deducted."
            )

        if order.stock_restored_at is not None:
            raise ValidationError("Stock has already been restored.")

        order_items = (
            OrderItem.objects
            .select_related("product")
            .filter(order=order)
            .order_by("pk")
        )

        if not order_items.exists():
            raise ValidationError(
                "Cannot approve cancellation without order items."
            )

        for item in order_items:
            if item.product is None:
                raise ValidationError(
                    f"Product for order item '{item.product_name}' "
                    "no longer exists."
                )

            InventoryService.increase_stock(
                product=item.product,
                quantity=item.quantity,
                reason=(
                    f"Stock restored for cancelled order "
                    f"{order.order_number}"
                ),
                created_by=admin_user,
            )

        order.stock_restored_at = timezone.now()

        # 5. Update the order status.
        order.status = Order.OrderStatus.CANCELLED
        order.save(
            update_fields=["status", "stock_restored_at", "updated_at"]
        )

        # 6. Record the order status change.
        OrderService.record_status_history(
            order=order,
            previous_status=previous_status,
            new_status=order.status,
            changed_by=admin_user,
            note=admin_note or "Cancellation approved by admin.",
        )

        # 7. Mark the cancellation request as approved.
        cancellation.status = OrderCancellation.CancellationStatus.APPROVED
        cancellation.admin_note = admin_note
        cancellation.reviewed_by = admin_user
        cancellation.reviewed_at = timezone.now()
        cancellation.save(
            update_fields=[
                "status",
                "admin_note",
                "reviewed_by",
                "reviewed_at",
            ]
        )

        return cancellation

    @staticmethod
    @transaction.atomic
    def reject_cancellation(cancellation_id, admin_user, admin_note=""):
        # 1. Lock the cancellation record.
        try:
            cancellation = (
                OrderCancellation.objects
                .select_for_update()
                .get(pk=cancellation_id)
            )
        except OrderCancellation.DoesNotExist:
            raise ValidationError(
                "Cancellation request does not exist."
            )

        # 2. Validate request.
        if cancellation.status != (
            OrderCancellation.CancellationStatus.REQUESTED
        ):
            raise ValidationError(
                "This cancellation request has already been processed."
            )

        # 3. Update cancellation history. Order status does not change.
        cancellation.status = OrderCancellation.CancellationStatus.REJECTED
        cancellation.admin_note = admin_note
        cancellation.reviewed_by = admin_user
        cancellation.reviewed_at = timezone.now()
        cancellation.save(
            update_fields=[
                "status",
                "admin_note",
                "reviewed_by",
                "reviewed_at",
            ]
        )

        return cancellation

    @staticmethod
    @transaction.atomic
    def update_order_status(order_id, new_status, admin_user, note=""):
        # 1. Lock the order row.
        try:
            order = Order.objects.select_for_update().get(pk=order_id)
        except Order.DoesNotExist:
            raise ValidationError("Order does not exist.")

        # 2. Allow only the intended forward transitions.
        allowed_transitions = {
            Order.OrderStatus.CONFIRMED: [
                Order.OrderStatus.PROCESSING,
            ],
            Order.OrderStatus.PROCESSING: [
                Order.OrderStatus.SHIPPED,
            ],
        }

        if new_status not in allowed_transitions.get(order.status, []):
            raise ValidationError(
                f"Cannot change order status from "
                f"{order.status} to {new_status}."
            )

        # 3. Do not progress an order with an active cancellation request.
        if OrderCancellation.objects.filter(
            order=order,
            status=OrderCancellation.CancellationStatus.REQUESTED,
        ).exists():
            raise ValidationError(
                "Resolve the pending cancellation request first."
            )

        previous_status = order.status
        order.status = new_status

        update_fields = ["status", "updated_at"]

        if new_status == Order.OrderStatus.SHIPPED:
            order.shipped_at = timezone.now()
            update_fields.append("shipped_at")

        order.save(update_fields=update_fields)

        # 4. Record the status change.
        OrderService.record_status_history(
            order=order,
            previous_status=previous_status,
            new_status=new_status,
            changed_by=admin_user,
            note=note,
        )

        return order
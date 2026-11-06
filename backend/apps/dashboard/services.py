from decimal import Decimal

from django.db.models import Count, Q, Sum

from apps.orders.models import Order
from apps.payments.models import Payment, Refund


class CustomerDashboardService:

    @staticmethod
    def get_overview(user):

        # 1. Customer profile
        profile = user.customer_profile

        # 2. Order statistics
        order_stats = (
            Order.objects
            .filter(user=user)
            .aggregate(
                total_orders=Count("id"),

                pending_orders=Count(
                    "id",
                    filter=Q(status=Order.OrderStatus.PENDING)
                ),

                confirmed_orders=Count(
                    "id",
                    filter=Q(status=Order.OrderStatus.CONFIRMED)
                ),

                processing_orders=Count(
                    "id",
                    filter=Q(status=Order.OrderStatus.PROCESSING)
                ),

                shipped_orders=Count(
                    "id",
                    filter=Q(status=Order.OrderStatus.SHIPPED)
                ),

                cancelled_orders=Count(
                    "id",
                    filter=Q(status=Order.OrderStatus.CANCELLED)
                ),
            )
        )

        # 3. Total successful payments
        successful_payments = (
            Payment.objects
            .filter(
                order__user=user,
                status=Payment.PaymentStatus.SUCCESS
            )
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        # 4. Total completed refunds
        completed_refunds = (
            Refund.objects
            .filter(
                payment__order__user=user,
                status=Refund.RefundStatus.COMPLETED
            )
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        # 5. Net customer spending
        total_spent = successful_payments - completed_refunds

        # 6. Latest five orders
        recent_orders = (
            Order.objects
            .filter(user=user)
            .prefetch_related("items")
            .order_by("-created_at")[:5]
        )

        return {
            "customer": {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone_number": profile.phone_number,
            },

            "statistics": {
                **order_stats,
                "total_spent": total_spent,
            },

            "recent_orders": recent_orders,
        }
        
from django.db.models import F
from django.utils import timezone

from apps.catalogue.models import Product
from apps.inventory.models import Inventory


class AdminDashboardService:

    @staticmethod
    def get_overview():

        now = timezone.now()
        today = now.date()

        month_start = today.replace(day=1)

        # Order statistics
        orders = Order.objects.all()

        order_stats = orders.aggregate(
            total_orders=Count("id"),

            pending_orders=Count(
                "id",
                filter=Q(status=Order.OrderStatus.PENDING),
            ),

            confirmed_orders=Count(
                "id",
                filter=Q(status=Order.OrderStatus.CONFIRMED),
            ),

            processing_orders=Count(
                "id",
                filter=Q(status=Order.OrderStatus.PROCESSING),
            ),

            shipped_orders=Count(
                "id",
                filter=Q(status=Order.OrderStatus.SHIPPED),
            ),

            cancelled_orders=Count(
                "id",
                filter=Q(status=Order.OrderStatus.CANCELLED),
            ),

            today_orders=Count(
                "id",
                filter=Q(created_at__date=today),
            ),

            monthly_orders=Count(
                "id",
                filter=Q(created_at__date__gte=month_start),
            ),
        )

        # Payment statistics
        successful_payments = Payment.objects.filter(
            status=Payment.PaymentStatus.SUCCESS
        )

        payment_stats = Payment.objects.aggregate(
            total_payments=Count("id"),

            successful_payments=Count(
                "id",
                filter=Q(status=Payment.PaymentStatus.SUCCESS),
            ),

            pending_payments=Count(
                "id",
                filter=Q(status=Payment.PaymentStatus.PENDING),
            ),

            failed_payments=Count(
                "id",
                filter=Q(status=Payment.PaymentStatus.FAILED),
            ),
        )

        total_revenue = (
            successful_payments.aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )

        today_revenue = (
            successful_payments.filter(
                created_at__date=today
            ).aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )

        monthly_revenue = (
            successful_payments.filter(
                created_at__date__gte=month_start
            ).aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )

        # Completed refunds
        completed_refunds = Refund.objects.filter(
            status=Refund.RefundStatus.COMPLETED
        )

        total_refunded = (
            completed_refunds.aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )

        pending_refunds = Refund.objects.filter(
            status=Refund.RefundStatus.PENDING
        ).count()

        processing_refunds = Refund.objects.filter(
            status=Refund.RefundStatus.PROCESSING
        ).count()

        # Net revenue
        net_revenue = total_revenue - total_refunded

        # Product statistics
        product_stats = Product.objects.aggregate(
            total_products=Count("id"),

            active_products=Count(
                "id",
                filter=Q(is_active=True),
            ),

            inactive_products=Count(
                "id",
                filter=Q(is_active=False),
            ),
        )

        # Inventory statistics
        inventory_stats = Inventory.objects.aggregate(
            total_inventory_items=Count("id"),

            low_stock_products=Count(
                "id",
                filter=Q(
                    quantity__gt=0,
                    quantity__lte=F("low_stock_threshold"),
                ),
            ),

            out_of_stock_products=Count(
                "id",
                filter=Q(quantity=0),
            ),
        )

        return {
            "sales": {
                "total_revenue": total_revenue,
                "today_revenue": today_revenue,
                "monthly_revenue": monthly_revenue,
                "total_refunded": total_refunded,
                "net_revenue": net_revenue,
            },

            "orders": order_stats,

            "products": product_stats,

            "inventory": inventory_stats,

            "payments": payment_stats,

            "refunds": {
                "pending_refunds": pending_refunds,
                "processing_refunds": processing_refunds,
                "completed_refunds": completed_refunds.count(),
                "total_refunded": total_refunded,
            },
        }
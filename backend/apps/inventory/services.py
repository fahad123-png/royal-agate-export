from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Inventory, StockMovement


class InventoryService:

    @staticmethod
    @transaction.atomic
    def increase_stock(
        product,
        quantity,
        reason="",
        created_by=None
    ):
        InventoryService._validate_quantity(quantity)

        inventory, _ = Inventory.objects.get_or_create(
            product=product
        )

        # Lock inventory row during update
        inventory = Inventory.objects.select_for_update().get(
            pk=inventory.pk
        )

        stock_before = inventory.quantity
        stock_after = stock_before + quantity

        inventory.quantity = stock_after
        inventory.save(update_fields=["quantity", "updated_at"])

        StockMovement.objects.create(
            inventory=inventory,
            movement_type=StockMovement.MovementType.INCREASE,
            quantity=quantity,
            stock_before=stock_before,
            stock_after=stock_after,
            reason=reason,
            created_by=created_by
        )

        return inventory

    @staticmethod
    @transaction.atomic
    def decrease_stock(
        product,
        quantity,
        reason="",
        created_by=None
    ):
        InventoryService._validate_quantity(quantity)

        inventory = (
            Inventory.objects.select_for_update()
            .filter(product=product)
            .first()
        )

        if inventory is None:
            raise ValidationError(
                "Inventory record does not exist."
            )

        stock_before = inventory.quantity

        if quantity > stock_before:
            raise ValidationError(
                f"Insufficient stock. Available quantity: {stock_before}."
            )

        stock_after = stock_before - quantity

        inventory.quantity = stock_after
        inventory.save(update_fields=["quantity", "updated_at"])

        StockMovement.objects.create(
            inventory=inventory,
            movement_type=StockMovement.MovementType.DECREASE,
            quantity=quantity,
            stock_before=stock_before,
            stock_after=stock_after,
            reason=reason,
            created_by=created_by
        )

        return inventory

    @staticmethod
    def get_stock(product):
        try:
            return Inventory.objects.get(product=product)
        except Inventory.DoesNotExist:
            return None

    @staticmethod
    def get_stock_movements(product):
        return StockMovement.objects.filter(
            inventory__product=product
        ).select_related(
            "inventory",
            "created_by"
        ).order_by("-created_at")
        
    @staticmethod
    def _validate_quantity(quantity):
        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, int)
            or quantity <= 0
        ):
            raise ValidationError(
                "Quantity must be a positive integer."
            )
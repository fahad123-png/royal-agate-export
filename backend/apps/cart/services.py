from django.db import transaction
from rest_framework.exceptions import ValidationError

from decimal import Decimal
from apps.catalogue.models import Product
from apps.inventory.models import Inventory

from .models import Cart, CartItem, CustomerAddress


class CartService:

    @staticmethod
    def get_or_create_cart(user):
        cart, _ = Cart.objects.get_or_create(user=user)
        return cart
    
    @staticmethod
    def _lock_cart(user):
        cart = CartService.get_or_create_cart(user)

        return Cart.objects.select_for_update().get(
            pk=cart.pk
        )

    @staticmethod
    def validate_product(product, purchase_mode, quantity, total_cart_quantity, inventory):
        """
        Validate product availability, purchase mode, price, MOQ and stock.
        """

        if not product.is_active:
            raise ValidationError({
                "product": "This product is currently unavailable."
            })

        if purchase_mode not in product.selling_modes:
            raise ValidationError({
                "purchase_mode": "This purchase mode is not available for this product."
            })

        if purchase_mode == CartItem.PurchaseMode.RETAIL:
            price = product.retail_price
            moq = product.retail_moq or 1

        elif purchase_mode == CartItem.PurchaseMode.WHOLESALE:
            price = product.wholesale_price
            moq = product.wholesale_moq or 10

        else:
            raise ValidationError({
                "purchase_mode": "Invalid purchase mode."
            })

        if price is None:
            raise ValidationError({
                "price": "Price is not available for this purchase mode."
            })

        if quantity < moq:
            raise ValidationError({
                "quantity": f"Minimum order quantity for this mode is {moq}."
            })

        if inventory is None:
            raise ValidationError({
                "stock": "Inventory record does not exist for this product."
            })

        # Check combined quantity across Retail and Wholesale cart items.
        if total_cart_quantity > inventory.quantity:
            raise ValidationError({
                "stock": (
                    f"Insufficient stock. Available: {inventory.quantity}, "
                    f"Requested in cart: {total_cart_quantity}."
                )
            })

        return price

    @staticmethod
    @transaction.atomic
    def add_item(user, product_id, purchase_mode, quantity):

        # 1. Lock customer's cart first.
        cart = CartService._lock_cart(user)

        # 2. Lock existing cart items in consistent order.
        locked_items = list(
            CartItem.objects.select_for_update()
            .filter(cart=cart)
            .order_by("id")
        )

        # 3. Lock product.
        try:
            product = Product.objects.select_for_update().get(
                id=product_id
            )
        except Product.DoesNotExist:
            raise ValidationError({
                "product_id": "Product does not exist."
            })

        # 4. Lock inventory.
        try:
            inventory = Inventory.objects.select_for_update().get(
                product=product
            )
        except Inventory.DoesNotExist:
            inventory = None

        # 5. Find existing item.
        existing_item = next(
            (
                item for item in locked_items
                if item.product_id == product.id
                and item.purchase_mode == purchase_mode
            ),
            None
        )

        final_quantity = quantity

        if existing_item:
            final_quantity += existing_item.quantity

        # 6. Calculate combined quantity across purchase modes.
        other_mode_quantity = sum(
            item.quantity
            for item in locked_items
            if item.product_id == product.id
            and item.purchase_mode != purchase_mode
        )

        total_cart_quantity = (
            other_mode_quantity + final_quantity
        )

        # 7. Validate product, MOQ, price and stock.
        CartService.validate_product(
            product=product,
            purchase_mode=purchase_mode,
            quantity=final_quantity,
            total_cart_quantity=total_cart_quantity,
            inventory=inventory
        )

        # 8. Update existing item or create a new one.
        if existing_item:
            existing_item.quantity = final_quantity
            existing_item.save(
                update_fields=["quantity", "updated_at"]
            )

            return existing_item, False

        item = CartItem.objects.create(
            cart=cart,
            product=product,
            purchase_mode=purchase_mode,
            quantity=quantity
        )

        return item, True

    @staticmethod
    @transaction.atomic
    def update_item(user, item_id, quantity):

        # 1. Lock customer's cart first.
        cart = CartService._lock_cart(user)

        # 2. Lock cart items in consistent order.
        locked_items = list(
            CartItem.objects.select_for_update()
            .filter(cart=cart)
            .order_by("id")
        )

        # 3. Find requested cart item.
        item = next(
            (cart_item for cart_item in locked_items
            if cart_item.id == item_id),
            None
        )

        if item is None:
            raise ValidationError({
                "item": "Cart item does not exist."
            })

        # 4. Lock product.
        product = Product.objects.select_for_update().get(
            id=item.product_id
        )

        # 5. Lock inventory.
        try:
            inventory = Inventory.objects.select_for_update().get(
                product=product
            )
        except Inventory.DoesNotExist:
            inventory = None

        # 6. Calculate combined quantity.
        other_mode_quantity = sum(
            cart_item.quantity
            for cart_item in locked_items
            if cart_item.id != item.id
            and cart_item.product_id == product.id
        )

        total_cart_quantity = other_mode_quantity + quantity

        # 7. Validate product, MOQ, price and stock.
        CartService.validate_product(
            product=product,
            purchase_mode=item.purchase_mode,
            quantity=quantity,
            total_cart_quantity=total_cart_quantity,
            inventory=inventory
        )

        # 8. Update quantity.
        item.quantity = quantity
        item.save(update_fields=["quantity", "updated_at"])

        return item

    @staticmethod
    @transaction.atomic
    def remove_item(user, item_id):

        # 1. Lock customer's cart.
        cart = CartService._lock_cart(user)

        # 2. Lock cart items.
        locked_items = list(
            CartItem.objects.select_for_update()
            .filter(cart=cart)
            .order_by("id")
        )

        # 3. Find requested item.
        item = next(
            (cart_item for cart_item in locked_items
            if cart_item.id == item_id),
            None
        )

        if item is None:
            raise ValidationError({
                "item": "Cart item does not exist."
            })

        # 4. Delete item.
        item.delete()

        return True

    @staticmethod
    @transaction.atomic
    def clear_cart(user):

        # 1. Lock customer's cart.
        cart = CartService._lock_cart(user)

        # 2. Lock cart items in consistent order.
        list(
            CartItem.objects.select_for_update()
            .filter(cart=cart)
            .order_by("id")
        )

        # 3. Delete all cart items.
        cart.items.all().delete()

        return True
    
    @staticmethod
    @transaction.atomic
    def validate_checkout(user, address_id):

        # 1. Lock customer's cart first.
        cart = CartService._lock_cart(user)

        # 2. Validate shipping address ownership.
        try:
            address = CustomerAddress.objects.get(
                id=address_id,
                user=user
            )
        except CustomerAddress.DoesNotExist:
            raise ValidationError({
                "address_id": "Invalid shipping address."
            })

        # 3. Lock and retrieve cart items.
        cart_items = list(
            CartItem.objects.select_for_update()
            .filter(cart=cart)
            .select_related("product")
            .prefetch_related("product__images")
            .order_by("product_id", "id")
        )

        if not cart_items:
            raise ValidationError({
                "cart": "Your cart is empty."
            })

        # 4. Lock products in a consistent order.
        product_ids = {
            item.product_id for item in cart_items
        }

        products = Product.objects.select_for_update().filter(
            id__in=product_ids
        ).order_by("id")

        product_map = {
            product.id: product for product in products
        }

        # 5. Lock inventory records in a consistent order.
        inventories = Inventory.objects.select_for_update().filter(
            product_id__in=product_ids
        ).order_by("product_id")

        inventory_map = {
            inventory.product_id: inventory
            for inventory in inventories
        }

        # 6. Calculate combined quantity per product.
        total_quantities = {}

        for item in cart_items:
            total_quantities[item.product_id] = (
                total_quantities.get(item.product_id, 0)
                + item.quantity
            )

        checkout_items = []
        subtotal = Decimal("0.00")
        total_items = 0

        # 7. Revalidate every cart item.
        for item in cart_items:

            product = product_map.get(item.product_id)

            if product is None:
                raise ValidationError({
                    "product": "A product in your cart no longer exists."
                })

            inventory = inventory_map.get(item.product_id)

            unit_price = CartService.validate_product(
                product=product,
                purchase_mode=item.purchase_mode,
                quantity=item.quantity,
                total_cart_quantity=total_quantities[item.product_id],
                inventory=inventory
            )

            item.product = product

            item_subtotal = unit_price * item.quantity

            subtotal += item_subtotal
            total_items += item.quantity

            checkout_items.append({
                "cart_item": item,
                "unit_price": unit_price,
                "subtotal": item_subtotal
            })

        return {
            "cart": cart,
            "address": address,
            "items": checkout_items,
            "total_items": total_items,
            "subtotal": subtotal,
            "total_amount": subtotal
        }
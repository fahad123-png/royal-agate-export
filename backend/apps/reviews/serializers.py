from rest_framework import serializers

from apps.reviews.models import Review

from apps.orders.models import OrderItem


class ReviewSerializer(serializers.ModelSerializer):

    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Review

        fields = [
            "id",
            "product",
            "customer_name",
            "rating",
            "title",
            "comment",
            "is_verified_purchase",
            "status",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "customer_name",
            "is_verified_purchase",
            "status",
            "created_at",
            "updated_at",
        ]

    def get_customer_name(self, obj):
        full_name = (
            f"{obj.user.first_name} {obj.user.last_name}"
        ).strip()

        return full_name or obj.user.email.split("@")[0]

    def validate_product(self, value):
        if not value.is_active:
            raise serializers.ValidationError(
                "Reviews cannot be submitted for inactive products."
            )

        return value
    
    def validate(self, attrs):
        # Product cannot be changed after review creation
        if (
            self.instance
            and "product" in attrs
            and attrs["product"].pk != self.instance.product_id
        ):
            raise serializers.ValidationError({
                "product": "You cannot change the product of an existing review."
            })

        # Prevent duplicate reviews for the same product
        product = attrs.get(
            "product",
            self.instance.product if self.instance else None
        )

        if product:
            existing_reviews = Review.objects.filter(
                user=self.context["request"].user,
                product=product
            )

            if self.instance:
                existing_reviews = existing_reviews.exclude(pk=self.instance.pk)

            if existing_reviews.exists():
                raise serializers.ValidationError(
                    "You have already submitted a review for this product."
                )

        return attrs

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError(
                "Rating must be between 1 and 5."
            )

        return value

    def validate_comment(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Review comment cannot be empty."
            )

        return value

    def create(self, validated_data):

        user = self.context["request"].user
        product = validated_data["product"]

        is_verified_purchase = OrderItem.objects.filter(
            order__user=user,
            product=product,
            order__status__in=[
                "CONFIRMED",
                "PROCESSING",
                "SHIPPED",
            ],
        ).exists()

        return Review.objects.create(
            user=user,
            is_verified_purchase=is_verified_purchase,
            status=Review.ReviewStatus.PENDING,
            **validated_data
        )

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)

        # Recalculate verified purchase status
        instance.is_verified_purchase = OrderItem.objects.filter(
            order__user=instance.user,
            product=instance.product,
            order__status__in=["CONFIRMED", "PROCESSING", "SHIPPED"],
        ).exists()

        # Edited reviews require moderation again
        instance.status = Review.ReviewStatus.PENDING
        instance.moderated_by = None
        instance.moderated_at = None
        instance.moderation_note = ""

        instance.save()
        return instance
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsCustomer, IsAdmin
from apps.catalogue.models import Product
from apps.reviews.models import Review
from apps.reviews.serializers import ReviewSerializer


# ==========================================
# PUBLIC: PRODUCT REVIEWS
# ==========================================

class ProductReviewListView(generics.ListAPIView):

    serializer_class = ReviewSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        product_id = self.request.query_params.get("product")
        
        if product_id and not product_id.isdigit():
            
            raise ValidationError({
                "product": "Product ID must be a valid number."
            })

        queryset = Review.objects.filter(
            status=Review.ReviewStatus.APPROVED,
            product__is_active=True
        ).select_related("user", "product")

        if product_id:
            queryset = queryset.filter(product_id=product_id)

        return queryset


# ==========================================
# PUBLIC: PRODUCT RATING SUMMARY
# ==========================================

class ProductRatingSummaryView(APIView):

    permission_classes = [AllowAny]

    def get(self, request, product_id):

        product = get_object_or_404(
            Product,
            pk=product_id,
            is_active=True
        )

        reviews = Review.objects.filter(
            product=product,
            status=Review.ReviewStatus.APPROVED
        )

        summary = reviews.aggregate(
            average_rating=Avg("rating"),
            total_reviews=Count("id")
        )

        distribution = {
            str(rating): 0
            for rating in range(1, 6)
        }

        rating_counts = reviews.values("rating").annotate(
            total=Count("id")
        )

        for item in rating_counts:
            distribution[str(item["rating"])] = item["total"]

        return Response({
            "product_id": product.id,
            "average_rating": round(
                summary["average_rating"] or 0,
                2
            ),
            "total_reviews": summary["total_reviews"],
            "rating_distribution": distribution
        })


# ==========================================
# CUSTOMER: CREATE REVIEW
# ==========================================

class CustomerReviewCreateView(generics.CreateAPIView):

    serializer_class = ReviewSerializer

    permission_classes = [
        IsAuthenticated,
        IsCustomer
    ]


# ==========================================
# CUSTOMER: MY REVIEWS
# ==========================================

class CustomerReviewListView(generics.ListAPIView):

    serializer_class = ReviewSerializer

    permission_classes = [
        IsAuthenticated,
        IsCustomer
    ]

    def get_queryset(self):
        return Review.objects.filter(
            user=self.request.user
        ).select_related("product", "user")


# ==========================================
# CUSTOMER: UPDATE / DELETE REVIEW
# ==========================================

class CustomerReviewDetailView(
    generics.RetrieveUpdateDestroyAPIView
):

    serializer_class = ReviewSerializer

    permission_classes = [
        IsAuthenticated,
        IsCustomer
    ]

    def get_queryset(self):
        return Review.objects.filter(
            user=self.request.user
        ).select_related("product", "user")


# ==========================================
# ADMIN: REVIEW MODERATION
# ==========================================

class AdminReviewListView(generics.ListAPIView):

    serializer_class = ReviewSerializer

    permission_classes = [
        IsAuthenticated,
        IsAdmin
    ]

    def get_queryset(self):
        queryset = Review.objects.all().select_related(
            "user",
            "product",
            "moderated_by"
        )

        review_status = self.request.query_params.get("status")

        if review_status:
            valid_statuses = [
                choice[0] for choice in Review.ReviewStatus.choices
            ]

            if review_status not in valid_statuses:
                
                raise ValidationError({
                    "status": "Invalid review status."
                })

            queryset = queryset.filter(status=review_status)

        return queryset


class AdminReviewModerationView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsAdmin
    ]

    def patch(self, request, pk):

        review = get_object_or_404(
            Review,
            pk=pk
        )

        action = request.data.get("action")
        moderation_note = request.data.get(
            "moderation_note",
            ""
        )
        
        if not isinstance(moderation_note, str):
            return Response(
                {"message": "Moderation note must be a string."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if action not in ["APPROVED", "REJECTED"]:
            return Response(
                {
                    "message": (
                        "Action must be APPROVED or REJECTED."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        review.status = action
        review.moderated_by = request.user
        review.moderated_at = timezone.now()
        review.moderation_note = moderation_note

        review.save(
            update_fields=[
                "status",
                "moderated_by",
                "moderated_at",
                "moderation_note",
                "updated_at"
            ]
        )

        return Response({
            "message": f"Review {action.lower()} successfully.",
            "review_id": review.id,
            "status": review.status
        })
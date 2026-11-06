from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.catalogue.models import Category, Product
from apps.orders.models import Order, OrderItem
from apps.reviews.models import Review


User = get_user_model()


class ReviewTestSetup(APITestCase):

    def setUp(self):
        self.customer = User.objects.create_user(
            username="customer1",
            email="customer@example.com",
            password="TestPassword123"
        )

        self.other_customer = User.objects.create_user(
            username="customer2",
            email="other@example.com",
            password="TestPassword123"
        )

        self.admin = User.objects.create_user(
            username="admin1",
            email="admin@example.com",
            password="TestPassword123",
            is_staff=True
        )

        self.category = Category.objects.create(
            name="Agate Stones"
        )

        self.product = Product.objects.create(
            name="Blue Agate",
            sku="AGATE001",
            category=self.category,
            retail_price=Decimal("500.00"),
            is_active=True
        )

        self.other_product = Product.objects.create(
            name="Black Agate",
            sku="AGATE002",
            category=self.category,
            retail_price=Decimal("700.00"),
            is_active=True
        )

        self.create_url = reverse("review-create")
        self.my_reviews_url = reverse("my-reviews")
        self.public_reviews_url = reverse("product-reviews")

        self.rating_summary_url = reverse(
            "product-rating-summary",
            kwargs={"product_id": self.product.id}
        )

        self.admin_reviews_url = reverse("admin-review-list")

        self.review_data = {
            "product": self.product.id,
            "rating": 5,
            "title": "Excellent Product",
            "comment": "Very good quality agate stone."
        }

    def create_review(self, user=None, product=None, **kwargs):
        user = user or self.customer
        product = product or self.product

        return Review.objects.create(
            user=user,
            product=product,
            rating=kwargs.get("rating", 5),
            title=kwargs.get("title", "Good Product"),
            comment=kwargs.get("comment", "Good quality product."),
            status=kwargs.get(
                "status",
                Review.ReviewStatus.PENDING
            ),
            is_verified_purchase=kwargs.get(
                "is_verified_purchase",
                False
            )
        )

    def create_order_with_item(self, user, product, order_status):
        order = Order.objects.create(
            order_number=f"ORD-{user.id}-{product.id}-{order_status}",
            user=user,
            shipping_full_name="Test Customer",
            shipping_phone_number="9876543210",
            shipping_address_line_1="Test Address",
            shipping_city="Ahmedabad",
            shipping_state="Gujarat",
            shipping_pincode="380001",
            subtotal=Decimal("500.00"),
            shipping_charge=Decimal("0.00"),
            discount=Decimal("0.00"),
            total_amount=Decimal("500.00"),
            status=order_status
        )

        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            product_sku=product.sku,
            purchase_mode=OrderItem.PurchaseMode.RETAIL,
            quantity=1,
            unit_price=Decimal("500.00"),
            subtotal=Decimal("500.00")
        )

        return order


# ==========================================
# CUSTOMER: CREATE REVIEW
# ==========================================

class ReviewCreateTests(ReviewTestSetup):

    def test_authenticated_customer_can_create_review(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            self.create_url,
            self.review_data,
            format="json"
        )

        self.assertEqual(response.status_code, 201)

        review = Review.objects.get(
            user=self.customer,
            product=self.product
        )

        self.assertEqual(review.status, Review.ReviewStatus.PENDING)
        self.assertEqual(review.rating, 5)

    def test_anonymous_user_cannot_create_review(self):
        response = self.client.post(
            self.create_url,
            self.review_data,
            format="json"
        )

        self.assertEqual(response.status_code, 401)

    def test_admin_cannot_create_customer_review(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            self.create_url,
            self.review_data,
            format="json"
        )

        self.assertEqual(response.status_code, 403)

    def test_duplicate_review_is_rejected(self):
        self.create_review()

        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            self.create_url,
            self.review_data,
            format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_review_for_inactive_product_is_rejected(self):
        self.product.is_active = False
        self.product.save()

        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            self.create_url,
            self.review_data,
            format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_rating_below_one_is_rejected(self):
        self.client.force_authenticate(user=self.customer)

        data = {
            **self.review_data,
            "rating": 0
        }

        response = self.client.post(
            self.create_url,
            data,
            format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_rating_above_five_is_rejected(self):
        self.client.force_authenticate(user=self.customer)

        data = {
            **self.review_data,
            "rating": 6
        }

        response = self.client.post(
            self.create_url,
            data,
            format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_empty_comment_is_rejected(self):
        self.client.force_authenticate(user=self.customer)

        data = {
            **self.review_data,
            "comment": "   "
        }

        response = self.client.post(
            self.create_url,
            data,
            format="json"
        )

        self.assertEqual(response.status_code, 400)


# ==========================================
# VERIFIED PURCHASE
# ==========================================

class VerifiedPurchaseTests(ReviewTestSetup):

    def test_confirmed_order_marks_review_verified(self):
        self.create_order_with_item(
            self.customer,
            self.product,
            Order.OrderStatus.CONFIRMED
        )

        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            self.create_url,
            self.review_data,
            format="json"
        )

        self.assertEqual(response.status_code, 201)

        review = Review.objects.get(user=self.customer)

        self.assertTrue(review.is_verified_purchase)

    def test_pending_order_does_not_mark_review_verified(self):
        self.create_order_with_item(
            self.customer,
            self.product,
            Order.OrderStatus.PENDING
        )

        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            self.create_url,
            self.review_data,
            format="json"
        )

        self.assertEqual(response.status_code, 201)

        review = Review.objects.get(user=self.customer)

        self.assertFalse(review.is_verified_purchase)


# ==========================================
# CUSTOMER: MY REVIEWS
# ==========================================

class CustomerReviewListTests(ReviewTestSetup):

    def test_customer_can_view_own_reviews(self):
        self.create_review()

        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.my_reviews_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_customer_cannot_view_other_customer_reviews(self):
        self.create_review(user=self.other_customer)

        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.my_reviews_url)

        self.assertEqual(response.data["count"], 0)

    def test_anonymous_user_cannot_view_my_reviews(self):
        response = self.client.get(self.my_reviews_url)

        self.assertEqual(response.status_code, 401)


# ==========================================
# CUSTOMER: UPDATE / DELETE REVIEW
# ==========================================

class CustomerReviewUpdateTests(ReviewTestSetup):

    def setUp(self):
        super().setUp()

        self.review = self.create_review(
            status=Review.ReviewStatus.APPROVED
        )

        self.detail_url = reverse(
            "my-review-detail",
            kwargs={"pk": self.review.id}
        )

    def test_customer_can_update_own_review(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.patch(
            self.detail_url,
            {
                "rating": 4,
                "comment": "Updated review comment."
            },
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        self.review.refresh_from_db()

        self.assertEqual(self.review.rating, 4)
        self.assertEqual(
            self.review.status,
            Review.ReviewStatus.PENDING
        )

    def test_customer_cannot_change_review_product(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.patch(
            self.detail_url,
            {"product": self.other_product.id},
            format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_customer_can_submit_same_product_id_during_update(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.patch(
            self.detail_url,
            {"product": self.product.id},
            format="json"
        )

        self.assertEqual(response.status_code, 200)

    def test_editing_review_resets_moderation(self):
        self.review.moderated_by = self.admin
        self.review.moderated_at = self.review.created_at
        self.review.moderation_note = "Previously approved"
        self.review.save()

        self.client.force_authenticate(user=self.customer)

        response = self.client.patch(
            self.detail_url,
            {"comment": "Updated comment."},
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        self.review.refresh_from_db()

        self.assertEqual(
            self.review.status,
            Review.ReviewStatus.PENDING
        )
        self.assertIsNone(self.review.moderated_by)
        self.assertIsNone(self.review.moderated_at)
        self.assertEqual(self.review.moderation_note, "")

    def test_customer_cannot_update_other_customer_review(self):
        other_review = self.create_review(
            user=self.other_customer
        )

        url = reverse(
            "my-review-detail",
            kwargs={"pk": other_review.id}
        )

        self.client.force_authenticate(user=self.customer)

        response = self.client.patch(
            url,
            {"rating": 2},
            format="json"
        )

        self.assertEqual(response.status_code, 404)

    def test_customer_can_delete_own_review(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            Review.objects.filter(pk=self.review.pk).exists()
        )


# ==========================================
# PUBLIC: PRODUCT REVIEWS
# ==========================================

class PublicReviewTests(ReviewTestSetup):

    def test_only_approved_reviews_are_public(self):
        self.create_review(
            status=Review.ReviewStatus.PENDING
        )

        self.create_review(
            user=self.other_customer,
            product=self.other_product,
            status=Review.ReviewStatus.APPROVED
        )

        self.client.force_authenticate(user=None)

        response = self.client.get(
            self.public_reviews_url,
            {"product": self.product.id}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_approved_review_is_public(self):
        self.create_review(
            status=Review.ReviewStatus.APPROVED
        )

        response = self.client.get(
            self.public_reviews_url,
            {"product": self.product.id}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_invalid_product_filter_returns_400(self):
        response = self.client.get(
            self.public_reviews_url,
            {"product": "invalid"}
        )

        self.assertEqual(response.status_code, 400)

    def test_inactive_product_reviews_are_not_public(self):
        self.product.is_active = False
        self.product.save()

        self.create_review(
            status=Review.ReviewStatus.APPROVED
        )

        response = self.client.get(
            self.public_reviews_url,
            {"product": self.product.id}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)


# ==========================================
# PRODUCT RATING SUMMARY
# ==========================================

class ProductRatingSummaryTests(ReviewTestSetup):

    def test_rating_summary_calculation(self):
        self.create_review(
            rating=5,
            status=Review.ReviewStatus.APPROVED
        )

        self.create_review(
            user=self.other_customer,
            rating=3,
            status=Review.ReviewStatus.APPROVED
        )

        response = self.client.get(self.rating_summary_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["average_rating"], 4.0)
        self.assertEqual(response.data["total_reviews"], 2)

        distribution = response.data["rating_distribution"]

        self.assertEqual(distribution["5"], 1)
        self.assertEqual(distribution["3"], 1)
        self.assertEqual(distribution["1"], 0)

    def test_pending_reviews_are_not_counted(self):
        self.create_review(
            status=Review.ReviewStatus.PENDING
        )

        response = self.client.get(self.rating_summary_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_reviews"], 0)
        self.assertEqual(response.data["average_rating"], 0)

    def test_inactive_product_rating_summary_returns_404(self):
        self.product.is_active = False
        self.product.save()

        response = self.client.get(self.rating_summary_url)

        self.assertEqual(response.status_code, 404)


# ==========================================
# ADMIN: REVIEW MODERATION
# ==========================================

class AdminReviewModerationTests(ReviewTestSetup):

    def setUp(self):
        super().setUp()

        self.review = self.create_review()

        self.moderation_url = reverse(
            "admin-review-moderate",
            kwargs={"pk": self.review.id}
        )

    def test_admin_can_view_all_reviews(self):
        self.create_review(
            user=self.other_customer,
            product=self.other_product,
            status=Review.ReviewStatus.APPROVED
        )

        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.admin_reviews_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

    def test_customer_cannot_access_admin_reviews(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.admin_reviews_url)

        self.assertEqual(response.status_code, 403)

    def test_admin_can_approve_review(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            self.moderation_url,
            {
                "action": "APPROVED",
                "moderation_note": "Review approved."
            },
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        self.review.refresh_from_db()

        self.assertEqual(
            self.review.status,
            Review.ReviewStatus.APPROVED
        )
        self.assertEqual(self.review.moderated_by, self.admin)
        self.assertIsNotNone(self.review.moderated_at)

    def test_admin_can_reject_review(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            self.moderation_url,
            {
                "action": "REJECTED",
                "moderation_note": "Inappropriate content."
            },
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        self.review.refresh_from_db()

        self.assertEqual(
            self.review.status,
            Review.ReviewStatus.REJECTED
        )

    def test_invalid_moderation_action_is_rejected(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            self.moderation_url,
            {"action": "PENDING"},
            format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_moderation_note_is_rejected(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            self.moderation_url,
            {
                "action": "APPROVED",
                "moderation_note": 123
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_customer_cannot_moderate_review(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.patch(
            self.moderation_url,
            {"action": "APPROVED"},
            format="json"
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_can_filter_reviews_by_status(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            self.admin_reviews_url,
            {"status": "PENDING"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_invalid_admin_status_filter_is_rejected(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            self.admin_reviews_url,
            {"status": "INVALID"}
        )

        self.assertEqual(response.status_code, 400)
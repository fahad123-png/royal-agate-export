from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from apps.content.models import ContentPage, FAQCategory, FAQ


class ContentPageAPITests(APITestCase):

    def setUp(self):
        self.list_url = reverse("content-page-list")

        self.published_page = ContentPage.objects.create(
            title="About Us",
            slug="about-us",
            content="About Royal Agate Export.",
            seo_title="About Royal Agate",
            seo_description="Learn about our company.",
            is_published=True,
        )

        self.draft_page = ContentPage.objects.create(
            title="Privacy Policy",
            slug="privacy-policy",
            content="Draft privacy policy.",
            is_published=False,
        )

    def get_results(self, response):
        if isinstance(response.data, dict):
            return response.data.get("results", response.data)

        return response.data

    def test_public_can_list_published_pages(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = self.get_results(response)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["slug"], "about-us")

    def test_draft_pages_are_not_visible(self):
        response = self.client.get(self.list_url)

        results = self.get_results(response)

        slugs = [page["slug"] for page in results]

        self.assertNotIn("privacy-policy", slugs)

    def test_published_page_detail(self):
        url = reverse(
            "content-page-detail",
            kwargs={"slug": "about-us"},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "About Us")

    def test_draft_page_detail_returns_404(self):
        url = reverse(
            "content-page-detail",
            kwargs={"slug": "privacy-policy"},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_slug_returns_404(self):
        url = reverse(
            "content-page-detail",
            kwargs={"slug": "invalid-page"},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_page_content_is_returned(self):
        url = reverse(
            "content-page-detail",
            kwargs={"slug": "about-us"},
        )

        response = self.client.get(url)

        self.assertEqual(
            response.data["content"],
            "About Royal Agate Export.",
        )

    def test_seo_information_is_returned(self):
        url = reverse(
            "content-page-detail",
            kwargs={"slug": "about-us"},
        )

        response = self.client.get(url)

        self.assertEqual(
            response.data["seo_title"],
            "About Royal Agate",
        )

        self.assertEqual(
            response.data["seo_description"],
            "Learn about our company.",
        )

    def test_internal_fields_are_not_exposed(self):
        url = reverse(
            "content-page-detail",
            kwargs={"slug": "about-us"},
        )

        response = self.client.get(url)

        self.assertNotIn("is_published", response.data)
        self.assertNotIn("updated_by", response.data)

    def test_page_list_requires_no_authentication(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_page_detail_requires_no_authentication(self):
        url = reverse(
            "content-page-detail",
            kwargs={"slug": "about-us"},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class FAQAPITests(APITestCase):

    def setUp(self):
        self.list_url = reverse("faq-list")

        self.shipping_category = FAQCategory.objects.create(
            name="Shipping",
            slug="shipping",
            is_active=True,
        )

        self.general_category = FAQCategory.objects.create(
            name="General",
            slug="general",
            is_active=True,
        )

        self.inactive_category = FAQCategory.objects.create(
            name="Archived",
            slug="archived",
            is_active=False,
        )

        self.published_faq = FAQ.objects.create(
            category=self.shipping_category,
            question="How long does shipping take?",
            answer="Shipping takes 5-7 business days.",
            is_published=True,
            sort_order=1,
        )

        self.general_faq = FAQ.objects.create(
            category=self.general_category,
            question="How can I contact you?",
            answer="Contact us through our website.",
            is_published=True,
            sort_order=2,
        )

        self.draft_faq = FAQ.objects.create(
            category=self.shipping_category,
            question="Draft shipping question?",
            answer="This is a draft answer.",
            is_published=False,
        )

        self.inactive_category_faq = FAQ.objects.create(
            category=self.inactive_category,
            question="Archived question?",
            answer="Archived answer.",
            is_published=True,
        )

    def get_results(self, response):
        if isinstance(response.data, dict):
            return response.data.get("results", response.data)

        return response.data

    def test_public_can_list_published_faqs(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = self.get_results(response)

        self.assertEqual(len(results), 2)

    def test_unpublished_faqs_are_hidden(self):
        response = self.client.get(self.list_url)

        results = self.get_results(response)

        questions = [faq["question"] for faq in results]

        self.assertNotIn(
            "Draft shipping question?",
            questions,
        )

    def test_inactive_category_faqs_are_hidden(self):
        response = self.client.get(self.list_url)

        results = self.get_results(response)

        questions = [faq["question"] for faq in results]

        self.assertNotIn("Archived question?", questions)

    def test_filter_faqs_by_category(self):
        response = self.client.get(
            self.list_url,
            {"category": "shipping"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = self.get_results(response)

        self.assertEqual(len(results), 1)

        self.assertEqual(
            results[0]["question"],
            "How long does shipping take?",
        )

    def test_general_category_filter(self):
        response = self.client.get(
            self.list_url,
            {"category": "general"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = self.get_results(response)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["category"]["slug"], "general")

    def test_invalid_category_returns_400(self):
        response = self.client.get(
            self.list_url,
            {"category": "invalid-category"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_inactive_category_filter_returns_400(self):
        response = self.client.get(
            self.list_url,
            {"category": "archived"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_faq_question_and_answer_are_returned(self):
        response = self.client.get(
            self.list_url,
            {"category": "shipping"},
        )

        results = self.get_results(response)

        self.assertEqual(
            results[0]["question"],
            "How long does shipping take?",
        )

        self.assertEqual(
            results[0]["answer"],
            "Shipping takes 5-7 business days.",
        )

    def test_faq_category_information_is_returned(self):
        response = self.client.get(
            self.list_url,
            {"category": "shipping"},
        )

        results = self.get_results(response)

        self.assertEqual(
            results[0]["category"]["name"],
            "Shipping",
        )

        self.assertEqual(
            results[0]["category"]["slug"],
            "shipping",
        )

    def test_internal_faq_fields_are_not_exposed(self):
        response = self.client.get(
            self.list_url,
            {"category": "shipping"},
        )

        results = self.get_results(response)

        self.assertNotIn("is_published", results[0])
        self.assertNotIn("updated_by", results[0])

    def test_faq_list_requires_no_authentication(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_faq_sort_order(self):
        response = self.client.get(self.list_url)

        results = self.get_results(response)

        sort_orders = [
            faq["sort_order"]
            for faq in results
        ]

        self.assertEqual(sort_orders, sorted(sort_orders))

    def test_empty_faq_category_returns_empty_list(self):
        category = FAQCategory.objects.create(
            name="Products",
            slug="products",
            is_active=True,
        )

        response = self.client.get(
            self.list_url,
            {"category": category.slug},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = self.get_results(response)

        self.assertEqual(len(results), 0)

    def test_faq_updated_at_is_returned(self):
        response = self.client.get(
            self.list_url,
            {"category": "shipping"},
        )

        results = self.get_results(response)

        self.assertIn("updated_at", results[0])
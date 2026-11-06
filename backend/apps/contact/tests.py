from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APITestCase

from apps.contact.models import ContactInquiry


User = get_user_model()


class ContactTestSetup(APITestCase):

    def setUp(self):
        cache.clear()

        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="TestPassword123",
            is_staff=True
        )

        self.customer = User.objects.create_user(
            username="customer",
            email="customer@example.com",
            password="TestPassword123"
        )

        self.submit_url = reverse("contact-submit")
        self.admin_list_url = reverse("admin-contact-inquiry-list")

        self.inquiry_data = {
            "name": "Test Customer",
            "email": "CUSTOMER@EXAMPLE.COM",
            "phone": "9876543210",
            "subject": "Product Inquiry",
            "message": "I want information about your agate products."
        }

    def create_inquiry(self, **kwargs):
        data = {
            "name": "Test Customer",
            "email": "customer@example.com",
            "phone": "9876543210",
            "subject": "Product Inquiry",
            "message": "I want information about agate products.",
        }

        data.update(kwargs)

        return ContactInquiry.objects.create(**data)


# ==========================================
# PUBLIC: SUBMIT INQUIRY
# ==========================================

class ContactInquiryCreateTests(ContactTestSetup):

    def test_anonymous_user_can_submit_inquiry(self):
        response = self.client.post(
            self.submit_url,
            self.inquiry_data,
            format="json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(ContactInquiry.objects.count(), 1)

    def test_authenticated_customer_can_submit_inquiry(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            self.submit_url,
            self.inquiry_data,
            format="json"
        )

        self.assertEqual(response.status_code, 201)

    def test_email_is_converted_to_lowercase(self):
        self.client.post(
            self.submit_url,
            self.inquiry_data,
            format="json"
        )

        inquiry = ContactInquiry.objects.get()

        self.assertEqual(
            inquiry.email,
            "customer@example.com"
        )

    def test_default_status_is_new(self):
        self.client.post(
            self.submit_url,
            self.inquiry_data,
            format="json"
        )

        inquiry = ContactInquiry.objects.get()

        self.assertEqual(
            inquiry.status,
            ContactInquiry.InquiryStatus.NEW
        )

    def test_customer_cannot_set_admin_notes(self):
        data = {
            **self.inquiry_data,
            "admin_notes": "Unauthorized note"
        }

        response = self.client.post(
            self.submit_url,
            data,
            format="json"
        )

        self.assertEqual(response.status_code, 201)

        inquiry = ContactInquiry.objects.get()

        self.assertEqual(inquiry.admin_notes, "")

    def test_customer_cannot_set_inquiry_status(self):
        data = {
            **self.inquiry_data,
            "status": "RESOLVED"
        }

        response = self.client.post(
            self.submit_url,
            data,
            format="json"
        )

        self.assertEqual(response.status_code, 201)

        inquiry = ContactInquiry.objects.get()

        self.assertEqual(
            inquiry.status,
            ContactInquiry.InquiryStatus.NEW
        )

    def test_empty_name_is_rejected(self):
        data = {
            **self.inquiry_data,
            "name": "   "
        }

        response = self.client.post(
            self.submit_url,
            data,
            format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_empty_subject_is_rejected(self):
        data = {
            **self.inquiry_data,
            "subject": "   "
        }

        response = self.client.post(
            self.submit_url,
            data,
            format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_empty_message_is_rejected(self):
        data = {
            **self.inquiry_data,
            "message": "   "
        }

        response = self.client.post(
            self.submit_url,
            data,
            format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_email_is_rejected(self):
        data = {
            **self.inquiry_data,
            "email": "invalid-email"
        }

        response = self.client.post(
            self.submit_url,
            data,
            format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_optional_phone_can_be_empty(self):
        data = {
            **self.inquiry_data,
            "phone": ""
        }

        response = self.client.post(
            self.submit_url,
            data,
            format="json"
        )

        self.assertEqual(response.status_code, 201)


# ==========================================
# ADMIN: LIST INQUIRIES
# ==========================================

class AdminContactInquiryListTests(ContactTestSetup):

    def test_admin_can_list_inquiries(self):
        self.create_inquiry()

        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.admin_list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_anonymous_user_cannot_list_inquiries(self):
        response = self.client.get(self.admin_list_url)

        self.assertEqual(response.status_code, 401)

    def test_customer_cannot_list_inquiries(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.admin_list_url)

        self.assertEqual(response.status_code, 403)

    def test_admin_can_filter_by_status(self):
        self.create_inquiry(
            subject="New Inquiry"
        )

        self.create_inquiry(
            subject="Resolved Inquiry",
            status=ContactInquiry.InquiryStatus.RESOLVED
        )

        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            self.admin_list_url,
            {"status": "RESOLVED"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_invalid_status_filter_is_rejected(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            self.admin_list_url,
            {"status": "INVALID"}
        )

        self.assertEqual(response.status_code, 400)

    def test_admin_can_search_inquiries(self):
        self.create_inquiry(
            name="Fahad Customer"
        )

        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            self.admin_list_url,
            {"search": "Fahad"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)


# ==========================================
# ADMIN: VIEW / UPDATE INQUIRY
# ==========================================

class AdminContactInquiryDetailTests(ContactTestSetup):

    def setUp(self):
        super().setUp()

        self.inquiry = self.create_inquiry()

        self.detail_url = reverse(
            "admin-contact-inquiry-detail",
            kwargs={"pk": self.inquiry.id}
        )

    def test_admin_can_view_inquiry_detail(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)

    def test_customer_cannot_view_inquiry_detail(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 403)

    def test_admin_can_update_inquiry_status(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            self.detail_url,
            {"status": "IN_PROGRESS"},
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        self.inquiry.refresh_from_db()

        self.assertEqual(
            self.inquiry.status,
            ContactInquiry.InquiryStatus.IN_PROGRESS
        )

    def test_admin_can_update_admin_notes(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            self.detail_url,
            {"admin_notes": "Customer contacted successfully."},
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        self.inquiry.refresh_from_db()

        self.assertEqual(
            self.inquiry.admin_notes,
            "Customer contacted successfully."
        )

    def test_admin_cannot_update_customer_details(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            self.detail_url,
            {"name": "Changed Name"},
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        self.inquiry.refresh_from_db()

        self.assertEqual(
            self.inquiry.name,
            "Test Customer"
        )

    def test_invalid_status_is_rejected(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            self.detail_url,
            {"status": "INVALID"},
            format="json"
        )

        self.assertEqual(response.status_code, 400)


# ==========================================
# RATE LIMITING
# ==========================================

class ContactInquiryThrottleTests(ContactTestSetup):

    def test_sixth_request_is_throttled(self):

        for request_number in range(5):
            response = self.client.post(
                self.submit_url,
                {
                    **self.inquiry_data,
                    "email": f"customer{request_number}@example.com"
                },
                format="json"
            )

            self.assertEqual(response.status_code, 201)

        response = self.client.post(
            self.submit_url,
            {
                **self.inquiry_data,
                "email": "sixth@example.com"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 429)
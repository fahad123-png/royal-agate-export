from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CustomerProfile


User = get_user_model()


class CustomerRegistrationTests(APITestCase):

    def setUp(self):
        self.url = reverse("customer-register")

        self.valid_data = {
            "first_name": "Fahad",
            "last_name": "Malek",
            "email": "fahad@example.com",
            "phone_number": "9876543210",
            "password": "StrongPass!2026X",
            "confirm_password": "StrongPass!2026X",
        }

    def test_customer_registration_success(self):
        response = self.client.post(
            self.url, self.valid_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            User.objects.filter(email="fahad@example.com").exists()
        )
        self.assertTrue(
            CustomerProfile.objects.filter(
                user__email="fahad@example.com"
            ).exists()
        )

    def test_duplicate_email_registration(self):
        self.client.post(self.url, self.valid_data, format="json")

        response = self.client.post(
            self.url, self.valid_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_mismatch(self):
        data = self.valid_data.copy()
        data["confirm_password"] = "DifferentPass!2026"

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_weak_password(self):
        data = self.valid_data.copy()
        data["password"] = "123"
        data["confirm_password"] = "123"

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_phone_number(self):
        data = self.valid_data.copy()
        data.pop("phone_number")

        response = self.client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CustomerLoginTests(APITestCase):

    def setUp(self):
        self.url = reverse("customer-login")

        self.user = User.objects.create_user(
            username="fahad",
            email="fahad@example.com",
            password="StrongPass!2026X",
            first_name="Fahad",
            last_name="Malek",
        )

        CustomerProfile.objects.create(
            user=self.user,
            phone_number="9876543210",
        )

    def test_customer_login_success(self):
        response = self.client.post(
            self.url,
            {
                "email": "fahad@example.com",
                "password": "StrongPass!2026X",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])

    def test_login_with_wrong_password(self):
        response = self.client.post(
            self.url,
            {
                "email": "fahad@example.com",
                "password": "WrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_with_invalid_email(self):
        response = self.client.post(
            self.url,
            {
                "email": "unknown@example.com",
                "password": "StrongPass!2026X",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inactive_user_login(self):
        self.user.is_active = False
        self.user.save()

        response = self.client.post(
            self.url,
            {
                "email": "fahad@example.com",
                "password": "StrongPass!2026X",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CustomerTokenRefreshTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="fahad",
            email="fahad@example.com",
            password="StrongPass!2026X",
        )

        self.refresh_token = str(RefreshToken.for_user(self.user))
        self.url = reverse("token-refresh")

    def test_token_refresh_success(self):
        response = self.client.post(
            self.url,
            {"refresh": self.refresh_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_token_refresh_invalid_token(self):
        response = self.client.post(
            self.url,
            {"refresh": "invalid-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CustomerLogoutTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="fahad",
            email="fahad@example.com",
            password="StrongPass!2026X",
        )

        self.refresh_token = str(RefreshToken.for_user(self.user))
        self.access_token = str(RefreshToken.for_user(self.user).access_token)

        self.url = reverse("customer-logout")

    def test_logout_success(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )

        response = self.client.post(
            self.url,
            {"refresh": self.refresh_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_without_authentication(self):
        response = self.client.post(
            self.url,
            {"refresh": self.refresh_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_logout_blacklists_refresh_token(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )

        response = self.client.post(
            self.url,
            {"refresh": self.refresh_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        refresh_response = self.client.post(
            reverse("token-refresh"),
            {"refresh": self.refresh_token},
            format="json",
        )

        self.assertEqual(
            refresh_response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_user_cannot_logout_another_users_token(self):
        another_user = User.objects.create_user(
            username="another",
            email="another@example.com",
            password="StrongPass!2026X",
        )

        another_refresh = str(RefreshToken.for_user(another_user))

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )

        response = self.client.post(
            self.url,
            {"refresh": another_refresh},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

class CustomerProfileTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="fahad",
            email="fahad@example.com",
            password="StrongPass!2026X",
            first_name="Fahad",
            last_name="Malek",
        )

        CustomerProfile.objects.create(
            user=self.user,
            phone_number="9876543210",
        )

        self.url = reverse("customer-profile")

        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )

    def test_get_customer_profile(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "fahad@example.com")

    def test_update_customer_profile(self):
        response = self.client.patch(
            self.url,
            {
                "first_name": "Mohammed",
                "phone_number": "9999999999",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.user.customer_profile.refresh_from_db()

        self.assertEqual(self.user.first_name, "Mohammed")
        self.assertEqual(
            self.user.customer_profile.phone_number,
            "9999999999",
        )

    def test_email_is_read_only(self):
        response = self.client.patch(
            self.url,
            {"email": "newemail@example.com"},
            format="json",
        )

        self.user.refresh_from_db()

        self.assertEqual(self.user.email, "fahad@example.com")

    def test_profile_requires_authentication(self):
        self.client.credentials()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
    def test_staff_cannot_access_customer_profile(self):
        staff_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass!2026X",
            is_staff=True,
        )

        refresh = RefreshToken.for_user(staff_user)
        staff_access_token = str(refresh.access_token)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {staff_access_token}"
        )

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_put_method_not_allowed(self):
        response = self.client.put(
            self.url,
            {
                "first_name": "Updated",
                "last_name": "Customer",
                "phone_number": "9999999999",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED
        )
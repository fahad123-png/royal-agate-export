from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from drf_spectacular.utils import extend_schema

from .serializers import CustomerRegistrationSerializer
from .serializers import CustomerLoginSerializer

from rest_framework_simplejwt.views import TokenRefreshView
from .serializers import CustomerTokenRefreshSerializer

from rest_framework.permissions import IsAuthenticated
from .serializers import CustomerLogoutSerializer

from rest_framework.generics import RetrieveUpdateAPIView

from .serializers import CustomerProfileSerializer
from .permissions import IsCustomer


class CustomerRegistrationView(generics.CreateAPIView):

    serializer_class = CustomerRegistrationSerializer
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Register a new customer",
        description="Create a customer account with profile information.",
        tags=["Authentication"]
    )
    def post(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        return Response(
            {
                "message": "Registration successful.",
                "user": {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "phone_number": user.customer_profile.phone_number
                }
            },
            status=status.HTTP_201_CREATED
        )

class CustomerLoginView(generics.GenericAPIView):

    serializer_class = CustomerLoginSerializer
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    @extend_schema(
        summary="Customer Login",
        description="Authenticate customer using email and password.",
        tags=["Authentication"]
    )
    def post(self, request, *args, **kwargs):

        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        tokens = serializer.validated_data["tokens"]

        return Response(
            {
                "message": "Login successful.",
                "user": {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email
                },
                "tokens": tokens
            },
            status=status.HTTP_200_OK
        )

class CustomerTokenRefreshView(TokenRefreshView):

    serializer_class = CustomerTokenRefreshSerializer

    @extend_schema(
        summary="Refresh JWT Access Token",
        description="Generate a new access token using a valid refresh token.",
        tags=["Authentication"]
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
    
class CustomerLogoutView(generics.GenericAPIView):

    serializer_class = CustomerLogoutSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Customer Logout",
        description="Blacklist the customer's refresh token.",
        tags=["Authentication"]
    )
    def post(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "Logout successful."},
            status=status.HTTP_200_OK
        )
        
class CustomerProfileView(RetrieveUpdateAPIView):

    serializer_class = CustomerProfileSerializer

    permission_classes = [IsCustomer]

    http_method_names = [
        "get",
        "patch",
        "head",
        "options"
    ]

    @extend_schema(
        summary="Get or update customer profile",
        description="Retrieve or partially update the authenticated customer's profile.",
        tags=["Authentication"]
    )
    def get_object(self):

        return self.request.user
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils.text import slugify

from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings


from rest_framework import serializers

from .models import CustomerProfile


User = get_user_model()


class CustomerRegistrationSerializer(serializers.Serializer):

    first_name = serializers.CharField(
        max_length=150,
        trim_whitespace=True
    )

    last_name = serializers.CharField(
        max_length=150,
        trim_whitespace=True
    )

    email = serializers.EmailField()

    phone_number = serializers.CharField(
        max_length=20,
        trim_whitespace=True
    )

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False
    )

    confirm_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False
    )

    def validate_email(self, value):
        email = User.objects.normalize_email(value).lower()

        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )

        return email

    def validate_phone_number(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "Phone number is required."
            )

        return value.strip()

    def validate(self, attrs):

        password = attrs.get("password")
        confirm_password = attrs.get("confirm_password")

        if password != confirm_password:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })

        # Validate password using Django password validators.
        user = User(
            username=attrs["email"].split("@")[0][:150],
            email=attrs["email"],
            first_name=attrs["first_name"],
            last_name=attrs["last_name"]
        )

        validate_password(password, user=user)

        return attrs

    def generate_username(self, email):

        base_username = slugify(
            email.split("@")[0]
        )[:140] or "customer"

        username = base_username
        counter = 1

        while User.objects.filter(
            username__iexact=username
        ).exists():

            username = f"{base_username}_{counter}"
            counter += 1

        return username

    @transaction.atomic
    def create(self, validated_data):

        validated_data.pop("confirm_password")

        password = validated_data.pop("password")
        phone_number = validated_data.pop("phone_number")

        username = self.generate_username(
            validated_data["email"]
        )

        # Create Django User.
        user = User.objects.create_user(
            username=username,
            password=password,
            **validated_data
        )

        # Create Customer Profile.
        CustomerProfile.objects.create(
            user=user,
            phone_number=phone_number
        )

        return user
    
class CustomerLoginSerializer(serializers.Serializer):

    email = serializers.EmailField()

    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False
    )

    def validate(self, attrs):

        email = attrs.get("email").lower()
        password = attrs.get("password")

        # Find user using email.
        user = User.objects.filter(
            email__iexact=email
        ).first()

        if user is None:
            raise serializers.ValidationError(
                "Invalid email or password."
            )

        # Authenticate using Django's authentication system.
        authenticated_user = authenticate(
            request=self.context.get("request"),
            username=user.username,
            password=password
        )

        if authenticated_user is None:
            raise serializers.ValidationError(
                "Invalid email or password."
            )

        if not authenticated_user.is_active:
            raise serializers.ValidationError(
                "This account is inactive."
            )

        # Generate JWT tokens.
        refresh = RefreshToken.for_user(authenticated_user)

        attrs["user"] = authenticated_user

        attrs["tokens"] = {
            "refresh": str(refresh),
            "access": str(refresh.access_token)
        }

        return attrs
    
class CustomerTokenRefreshSerializer(TokenRefreshSerializer):
    pass

class CustomerLogoutSerializer(serializers.Serializer):

    refresh = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            token = RefreshToken(attrs["refresh"])

        except TokenError:
            raise serializers.ValidationError({
                "refresh": "Invalid or expired refresh token."
            })

        request = self.context.get("request")

        if request is None or not request.user.is_authenticated:
            raise serializers.ValidationError({
                "refresh": "Authenticated user is required."
            })

        token_user_id = token.get(api_settings.USER_ID_CLAIM)

        if str(token_user_id) != str(request.user.pk):
            raise serializers.ValidationError({
                "refresh": "You cannot logout another user's session."
            })

        self.token = token

        return attrs

    def save(self, **kwargs):
        try:
            self.token.blacklist()

        except TokenError:
            raise serializers.ValidationError({
                "refresh": "Invalid or expired refresh token."
            })
            
class CustomerProfileSerializer(serializers.Serializer):

    id = serializers.IntegerField(read_only=True)

    first_name = serializers.CharField(
        max_length=150,
        required=False
    )

    last_name = serializers.CharField(
        max_length=150,
        required=False
    )

    email = serializers.EmailField(read_only=True)

    phone_number = serializers.CharField(
        max_length=20,
        required=False,
        trim_whitespace=True
    )

    def to_representation(self, instance):

        profile = instance.customer_profile

        return {
            "id": instance.id,
            "first_name": instance.first_name,
            "last_name": instance.last_name,
            "email": instance.email,
            "phone_number": profile.phone_number
        }

    @transaction.atomic
    def update(self, instance, validated_data):

        instance.first_name = validated_data.get(
            "first_name",
            instance.first_name
        )

        instance.last_name = validated_data.get(
            "last_name",
            instance.last_name
        )

        instance.save(
            update_fields=["first_name", "last_name"]
        )

        profile = instance.customer_profile

        profile.phone_number = validated_data.get(
            "phone_number",
            profile.phone_number
        )

        profile.save(
            update_fields=["phone_number"]
        )

        return instance
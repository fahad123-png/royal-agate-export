from rest_framework import serializers

from apps.contact.models import ContactInquiry


class ContactInquiryCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = ContactInquiry

        fields = [
            "id",
            "name",
            "email",
            "phone",
            "subject",
            "message",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
        ]

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Name cannot be empty."
            )

        return value

    def validate_email(self, value):
        return value.strip().lower()

    def validate_phone(self, value):
        return value.strip()

    def validate_subject(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Subject cannot be empty."
            )

        return value

    def validate_message(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Message cannot be empty."
            )

        return value


class ContactInquiryAdminSerializer(serializers.ModelSerializer):

    class Meta:
        model = ContactInquiry

        fields = [
            "id",
            "name",
            "email",
            "phone",
            "subject",
            "message",
            "status",
            "admin_notes",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "name",
            "email",
            "phone",
            "subject",
            "message",
            "created_at",
            "updated_at",
        ]

    def validate_status(self, value):
        valid_statuses = [
            choice[0]
            for choice in ContactInquiry.InquiryStatus.choices
        ]

        if value not in valid_statuses:
            raise serializers.ValidationError(
                "Invalid inquiry status."
            )

        return value
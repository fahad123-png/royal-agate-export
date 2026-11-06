from django.db import models


class ContactInquiry(models.Model):

    class InquiryStatus(models.TextChoices):
        NEW = "NEW", "New"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        RESOLVED = "RESOLVED", "Resolved"

    # Customer Information
    name = models.CharField(max_length=150)

    email = models.EmailField()

    phone = models.CharField(
        max_length=20,
        blank=True
    )

    # Inquiry Information
    subject = models.CharField(max_length=200)

    message = models.TextField()

    # Admin Management
    status = models.CharField(
        max_length=20,
        choices=InquiryStatus.choices,
        default=InquiryStatus.NEW,
        db_index=True
    )

    admin_notes = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Contact Inquiry"
        verbose_name_plural = "Contact Inquiries"

    def __str__(self):
        return f"{self.subject} - {self.email}"
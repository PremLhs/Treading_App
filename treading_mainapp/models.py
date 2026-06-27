from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    mobile = models.CharField(
        max_length=15,
        unique=True,
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.mobile}"


class GapUpStatus(models.Model):
    GAP_CHOICES = (
        ("GAP UP", "GAP UP"),
        ("GAP DOWN", "GAP DOWN"),
        ("NO GAP", "NO GAP"),
        ("SCAN FAILED", "SCAN FAILED"),
    )

    symbol = models.CharField(max_length=32, db_index=True)
    company_name = models.CharField(max_length=128, blank=True, default="")
    trade_date = models.DateField(db_index=True)

    prev_trade_date = models.DateField(null=True, blank=True)

    prev_open = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    prev_high = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    prev_low = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    prev_close = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    today_open = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    today_high = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    today_low = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    today_close = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    open_diff = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    high_diff = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    low_diff = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    close_diff = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    gap_up = models.BooleanField(default=False)
    gap_down = models.BooleanField(default=False)
    gap_type = models.CharField(max_length=20, choices=GAP_CHOICES, default="NO GAP")
    notes = models.TextField(blank=True, default="")

    candle_start = models.TimeField(null=True, blank=True)
    candle_end = models.TimeField(null=True, blank=True)

    data_source = models.CharField(max_length=50, blank=True, default="")
    refreshed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("symbol", "trade_date")
        ordering = ["symbol"]

    def __str__(self):
        return f"{self.symbol} - {self.trade_date} - {self.gap_type}"
    


###############################################################################

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class WhatsAppContact(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wa_contacts")
    name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, db_index=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    source_file = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("owner", "phone")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name or 'Unknown'} - {self.phone}"


class WhatsAppCampaign(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("queued", "Queued"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wa_campaigns")
    campaign_name = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    media_file = models.FileField(upload_to="whatsapp_broadcasts/", blank=True, null=True)
    media_type = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    total_contacts = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.campaign_name


class WhatsAppMessageLog(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
    ]

    campaign = models.ForeignKey(WhatsAppCampaign, on_delete=models.CASCADE, related_name="logs")
    contact = models.ForeignKey(WhatsAppContact, on_delete=models.CASCADE, related_name="message_logs")
    phone = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    whatsapp_message_id = models.CharField(max_length=255, blank=True)
    response_code = models.PositiveIntegerField(default=0)
    response_body = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.campaign.campaign_name} - {self.phone} - {self.status}"
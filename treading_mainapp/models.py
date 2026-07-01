from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone


User = get_user_model()


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    mobile = models.CharField(
        max_length=15,
        unique=True,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user.username} - {self.mobile}"


class GapUpStatus(models.Model):
    class GapType(models.TextChoices):
        GAP_UP = "GAP UP", "GAP UP"
        GAP_DOWN = "GAP DOWN", "GAP DOWN"
        NO_GAP = "NO GAP", "NO GAP"
        SCAN_FAILED = "SCAN FAILED", "SCAN FAILED"

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
    gap_type = models.CharField(
        max_length=20,
        choices=GapType.choices,
        default=GapType.NO_GAP,
        db_index=True,
    )
    notes = models.TextField(blank=True, default="")

    candle_start = models.TimeField(null=True, blank=True)
    candle_end = models.TimeField(null=True, blank=True)

    data_source = models.CharField(max_length=50, blank=True, default="")
    refreshed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["symbol"]
        constraints = [
            models.UniqueConstraint(fields=["symbol", "trade_date"], name="uniq_gap_status_symbol_trade_date"),
        ]
        indexes = [
            models.Index(fields=["trade_date", "symbol"], name="idx_gap_trade_symbol"),
            models.Index(fields=["trade_date", "gap_type"], name="idx_gap_trade_type"),
            models.Index(fields=["trade_date", "gap_up"], name="idx_gap_trade_gapup"),
            models.Index(fields=["trade_date", "gap_down"], name="idx_gap_trade_gapdown"),
        ]

    def __str__(self):
        return f"{self.symbol} - {self.trade_date} - {self.gap_type}"


class GapScanRun(models.Model):
    class ScanType(models.TextChoices):
        AUTO_0930 = "AUTO_0930", "Auto 09:30"
        MANUAL = "MANUAL", "Manual"
        FORCE = "FORCE", "Force"
        FINAL = "FINAL", "Final"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    trade_date = models.DateField(db_index=True)
    scan_type = models.CharField(
        max_length=20,
        choices=ScanType.choices,
        default=ScanType.MANUAL,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    last_heartbeat = models.DateTimeField(null=True, blank=True)

    success_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    total_count = models.PositiveIntegerField(default=0)

    trigger_source = models.CharField(max_length=50, blank=True, default="")
    message = models.TextField(blank=True, default="")
    lock_token = models.CharField(max_length=64, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-trade_date", "-started_at", "-id"]
        indexes = [
            models.Index(fields=["trade_date", "status"], name="idx_scanrun_trade_status"),
            models.Index(fields=["trade_date", "scan_type"], name="idx_scanrun_trade_type"),
        ]

    def __str__(self):
        return f"{self.trade_date} | {self.scan_type} | {self.status}"

    @property
    def is_running(self):
        return self.status == self.Status.RUNNING

    @property
    def is_stale_running(self):
        if self.status != self.Status.RUNNING or not self.last_heartbeat:
            return False
        return (timezone.now() - self.last_heartbeat).total_seconds() > 900


class WhatsAppContact(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wa_contacts")
    name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, db_index=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    source_file = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "phone"], name="uniq_wa_contact_owner_phone"),
        ]
        indexes = [
            models.Index(fields=["owner", "is_active"], name="idx_wa_contact_owner_active"),
        ]

    def __str__(self):
        return f"{self.name or 'Unknown'} - {self.phone}"


class WhatsAppCampaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wa_campaigns")
    campaign_name = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    media_file = models.FileField(upload_to="whatsapp_broadcasts/", blank=True, null=True)
    media_type = models.CharField(max_length=20, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    total_contacts = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"], name="idx_wa_campaign_owner_status"),
        ]

    def __str__(self):
        return self.campaign_name


class WhatsAppMessageLog(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    campaign = models.ForeignKey(WhatsAppCampaign, on_delete=models.CASCADE, related_name="logs")
    contact = models.ForeignKey(WhatsAppContact, on_delete=models.CASCADE, related_name="message_logs")
    phone = models.CharField(max_length=20, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    whatsapp_message_id = models.CharField(max_length=255, blank=True)
    response_code = models.PositiveIntegerField(default=0)
    response_body = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["campaign", "status"], name="idx_wa_log_campaign_status"),
            models.Index(fields=["contact", "status"], name="idx_wa_log_contact_status"),
        ]

    def __str__(self):
        return f"{self.campaign.campaign_name} - {self.phone} - {self.status}"
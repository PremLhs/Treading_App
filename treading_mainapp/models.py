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




#############################################################################
from django.db import models


class GapUpStatus(models.Model):
    GAP_CHOICES = (
        ("GAP UP", "GAP UP"),
        ("GAP DOWN", "GAP DOWN"),
        ("NO GAP", "NO GAP"),
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
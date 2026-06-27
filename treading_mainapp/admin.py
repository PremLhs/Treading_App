from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "mobile", "created_at")
    search_fields = ("user__username", "mobile")
    list_filter = ("created_at",)

#############################################################
from django.contrib import admin
from .models import WhatsAppContact, WhatsAppCampaign, WhatsAppMessageLog


@admin.register(WhatsAppContact)
class WhatsAppContactAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "phone", "email", "is_active", "created_at")
    search_fields = ("name", "phone", "email")
    list_filter = ("is_active", "created_at")


@admin.register(WhatsAppCampaign)
class WhatsAppCampaignAdmin(admin.ModelAdmin):
    list_display = ("id", "campaign_name", "owner", "status", "total_contacts", "sent_count", "failed_count", "created_at")
    search_fields = ("campaign_name",)
    list_filter = ("status", "created_at")


@admin.register(WhatsAppMessageLog)
class WhatsAppMessageLogAdmin(admin.ModelAdmin):
    list_display = ("id", "campaign", "phone", "status", "response_code", "sent_at", "created_at")
    search_fields = ("phone", "whatsapp_message_id")
    list_filter = ("status", "created_at", "sent_at")
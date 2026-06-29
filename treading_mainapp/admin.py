

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0


class CustomUserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

admin.site.register(User, CustomUserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "mobile")
    search_fields = ("user__username", "user__email", "mobile")
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


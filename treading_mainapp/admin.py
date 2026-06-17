from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "mobile", "created_at")
    search_fields = ("user__username", "mobile")
    list_filter = ("created_at",)
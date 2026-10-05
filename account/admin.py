from django.contrib import admin
from django.utils.html import format_html
from .models import User, Profile, CreatorDocument


class CreatorDocumentInline(admin.TabularInline):
    model = CreatorDocument
    extra = 0
    readonly_fields = ["document_preview", "uploaded_at"]
    fields = ["document_type", "document", "document_preview", "uploaded_at"]

    def document_preview(self, obj):
        if not obj.document:
            return "No file attached"
        return format_html('<a href="{}" target="_blank">View File</a>', obj.document.url)
    document_preview.short_description = "Preview"


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["email", "phone", "is_verified", "is_staff"]
    search_fields = ["email", "phone"]


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "full_name", "phone_display", "is_creator_ready", "created_at"]
    search_fields = ["full_name", "user__email", "user__phone"]
    inlines = [CreatorDocumentInline]

    def phone_display(self, obj):
        return obj.user.phone
    phone_display.short_description = "Phone"


@admin.register(CreatorDocument)
class CreatorDocumentAdmin(admin.ModelAdmin):
    list_display = ["id", "profile", "document_type", "uploaded_at"]
    search_fields = ["profile__full_name", "profile__user__email"]
    list_filter = ["document_type", "uploaded_at"]
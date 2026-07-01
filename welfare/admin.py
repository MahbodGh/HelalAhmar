from django.contrib import admin

from welfare.models import WelfareNote


@admin.register(WelfareNote)
class WelfareNoteAdmin(admin.ModelAdmin):
    list_display = ("personnel", "category", "author", "created_at")
    list_filter = ("category",)
    search_fields = ("personnel__first_name", "personnel__last_name", "personnel__national_id", "text")
    autocomplete_fields = ("personnel", "author")

from django.contrib import admin

from finance.models import DeductionBatch, DeductionItem


class DeductionItemInline(admin.TabularInline):
    model = DeductionItem
    extra = 0
    autocomplete_fields = ("personnel",)
    readonly_fields = ("source_type", "source_ref")


@admin.register(DeductionBatch)
class DeductionBatchAdmin(admin.ModelAdmin):
    list_display = ("period", "title", "org_unit", "status", "item_count", "total_amount")
    list_filter = ("status", "period")
    search_fields = ("period", "title")
    autocomplete_fields = ("org_unit", "created_by")
    readonly_fields = ("total_amount", "item_count", "generated_at", "finalized_at", "exported_at")
    inlines = [DeductionItemInline]


@admin.register(DeductionItem)
class DeductionItemAdmin(admin.ModelAdmin):
    list_display = ("batch", "personnel", "source_type", "amount")
    list_filter = ("source_type",)
    search_fields = ("personnel__first_name", "personnel__last_name", "personnel__national_id", "source_ref")
    autocomplete_fields = ("batch", "personnel")

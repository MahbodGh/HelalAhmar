from django.contrib import admin

from referral.models import ContractedProvider, ReferralLetter


@admin.register(ContractedProvider)
class ContractedProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "category", "discount_percent", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name", "code")
    autocomplete_fields = ("province", "city")


@admin.register(ReferralLetter)
class ReferralLetterAdmin(admin.ModelAdmin):
    list_display = ("code", "personnel", "provider", "status", "issued_at", "valid_until")
    list_filter = ("status", "provider")
    search_fields = ("code", "personnel__first_name", "personnel__last_name", "personnel__national_id")
    autocomplete_fields = ("provider", "personnel", "beneficiary_dependent", "created_by", "issued_by")
    readonly_fields = ("code", "issued_at")

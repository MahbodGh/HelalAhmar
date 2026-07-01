from django.contrib import admin

from insurance.models import InsuranceClaim, InsurancePlan, InsuranceRequest


@admin.register(InsurancePlan)
class InsurancePlanAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "insurer_name", "premium_per_person", "is_active")
    list_filter = ("is_active", "allow_dependents")
    search_fields = ("name", "code", "insurer_name")


@admin.register(InsuranceRequest)
class InsuranceRequestAdmin(admin.ModelAdmin):
    list_display = ("code", "personnel", "plan", "premium_total", "status", "submitted_at")
    list_filter = ("status", "plan")
    search_fields = ("code", "personnel__first_name", "personnel__last_name", "personnel__national_id")
    autocomplete_fields = ("plan", "personnel", "created_by", "reviewed_by")
    filter_horizontal = ("insured_dependents",)
    readonly_fields = ("code", "premium_total", "submitted_at", "reviewed_at")


@admin.register(InsuranceClaim)
class InsuranceClaimAdmin(admin.ModelAdmin):
    list_display = ("code", "personnel", "service_type", "claimed_amount", "approved_amount", "status", "submitted_at")
    list_filter = ("status",)
    search_fields = ("code", "personnel__first_name", "personnel__last_name", "personnel__national_id", "service_type")
    autocomplete_fields = ("request", "personnel", "patient_dependent", "created_by", "reviewed_by")
    readonly_fields = ("code", "submitted_at", "reviewed_at", "paid_at")

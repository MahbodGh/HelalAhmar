from django.contrib import admin

from loan.models import LoanRequest, LoanType


@admin.register(LoanType)
class LoanTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "max_amount", "max_installments", "profit_rate", "fund_budget", "is_active")
    list_filter = ("is_active", "allocation_method")
    search_fields = ("name", "code")


@admin.register(LoanRequest)
class LoanRequestAdmin(admin.ModelAdmin):
    list_display = ("code", "personnel", "loan_type", "requested_amount", "approved_amount", "monthly_installment", "status")
    list_filter = ("status", "loan_type")
    search_fields = ("code", "personnel__first_name", "personnel__last_name", "personnel__national_id")
    autocomplete_fields = ("loan_type", "personnel", "created_by", "reviewed_by")
    readonly_fields = ("code", "monthly_installment", "submitted_at", "reviewed_at", "disbursed_at")

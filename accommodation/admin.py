from django.contrib import admin

from accommodation.models import (
    AccommodationComplex,
    AccommodationUnit,
    Amenity,
    LotteryEnrollment,
    LotteryRun,
    Reservation,
    ReservationPeriod,
    SeasonalRate,
    UnitPlan,
)


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ("name", "scope", "icon", "is_active")
    list_filter = ("scope", "is_active")
    search_fields = ("name",)


@admin.register(UnitPlan)
class UnitPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "is_management")
    search_fields = ("name",)


class UnitInline(admin.TabularInline):
    model = AccommodationUnit
    extra = 0
    fields = ("name_or_number", "plan", "standard_capacity", "max_capacity", "status", "is_management")


@admin.register(AccommodationComplex)
class ComplexAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "province", "city", "is_active")
    list_filter = ("is_active", "province")
    search_fields = ("name", "code", "address")
    autocomplete_fields = ("org_unit", "province", "city", "manager", "executive_officer", "services_officer")
    filter_horizontal = ("general_amenities", "housekeeping_staff")
    inlines = [UnitInline]


class SeasonalRateInline(admin.TabularInline):
    model = SeasonalRate
    extra = 0


@admin.register(AccommodationUnit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("name_or_number", "complex", "plan", "standard_capacity", "max_capacity", "status", "is_management")
    list_filter = ("status", "is_management", "plan", "complex")
    search_fields = ("name_or_number", "complex__name")
    autocomplete_fields = ("complex", "plan")
    filter_horizontal = ("amenities",)
    inlines = [SeasonalRateInline]


@admin.register(ReservationPeriod)
class ReservationPeriodAdmin(admin.ModelAdmin):
    list_display = ("title", "method", "status", "enroll_start", "enroll_end", "stay_from", "stay_to")
    list_filter = ("method", "status")
    search_fields = ("title",)
    filter_horizontal = ("units",)
    autocomplete_fields = ("org_unit", "province")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("code", "personnel", "unit", "check_in_date", "check_out_date", "nights", "total_cost", "status")
    list_filter = ("status", "period")
    search_fields = ("code", "personnel__first_name", "personnel__last_name", "personnel__national_id")
    autocomplete_fields = ("period", "unit", "personnel", "created_by")
    readonly_fields = ("code", "nights", "total_cost", "payment_deadline")


@admin.register(LotteryEnrollment)
class LotteryEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("period", "personnel", "persons", "score", "status", "result_reservation")
    list_filter = ("status", "period")
    search_fields = ("personnel__first_name", "personnel__last_name", "personnel__national_id")
    autocomplete_fields = ("period", "personnel", "created_by", "result_reservation")
    filter_horizontal = ("preferred_units",)


@admin.register(LotteryRun)
class LotteryRunAdmin(admin.ModelAdmin):
    list_display = ("period", "total_enrollments", "winners_count", "seed", "created_at")
    list_filter = ("period",)
    readonly_fields = ("total_enrollments", "winners_count", "seed")

from django.contrib import admin

from accommodation.models import (
    AccommodationComplex,
    AccommodationUnit,
    Amenity,
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

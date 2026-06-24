from django.contrib import admin

from hr.models import City, Dependent, OrgUnit, Personnel, PersonnelDecree, Province


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "province", "code")
    list_filter = ("province",)
    search_fields = ("name",)


@admin.register(OrgUnit)
class OrgUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "type", "parent", "province", "is_active")
    list_filter = ("type", "is_active", "province")
    search_fields = ("name", "code")
    autocomplete_fields = ("parent", "province", "city")


class DependentInline(admin.TabularInline):
    model = Dependent
    extra = 0


class PersonnelDecreeInline(admin.TabularInline):
    model = PersonnelDecree
    extra = 0


@admin.register(Personnel)
class PersonnelAdmin(admin.ModelAdmin):
    list_display = ("personnel_no", "full_name", "national_id", "employment_type", "employment_status", "org_unit", "province")
    list_filter = ("employment_type", "employment_status", "is_retired", "province")
    search_fields = ("first_name", "last_name", "national_id", "personnel_no")
    autocomplete_fields = ("org_unit", "province")
    inlines = [DependentInline, PersonnelDecreeInline]


@admin.register(Dependent)
class DependentAdmin(admin.ModelAdmin):
    list_display = ("full_name", "relation", "national_id", "personnel")
    list_filter = ("relation", "is_student")
    search_fields = ("first_name", "last_name", "national_id")
    autocomplete_fields = ("personnel",)


@admin.register(PersonnelDecree)
class PersonnelDecreeAdmin(admin.ModelAdmin):
    list_display = ("personnel", "title", "decree_no", "decree_date")
    search_fields = ("decree_no", "title")
    autocomplete_fields = ("personnel",)

"""Seed common amenities and unit plans. Run: python manage.py seed_accommodation"""
from django.core.management.base import BaseCommand
from django.db import transaction

from accommodation.models import Amenity, UnitPlan

GENERAL_AMENITIES = ["پارکینگ", "رستوران", "اینترنت", "فضای بازی کودکان", "نمازخانه", "لابی", "آسانسور"]
UNIT_AMENITIES = ["سیستم سرمایشی/گرمایشی", "تلویزیون", "یخچال", "حوله", "چای‌ساز", "لوازم بهداشتی", "سشوار", "گاوصندوق"]
PLANS = [
    ("سوئیت", False), ("اتاق دوتخته", False), ("اتاق چهارتخته", False),
    ("کلبه", False), ("تخت (خوابگاهی)", False), ("سوئیت مدیریتی", True),
]


class Command(BaseCommand):
    help = "Seed amenities and unit plans (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        for name in GENERAL_AMENITIES:
            Amenity.objects.get_or_create(name=name, scope="general", defaults={"is_active": True})
        for name in UNIT_AMENITIES:
            Amenity.objects.get_or_create(name=name, scope="unit", defaults={"is_active": True})
        self.stdout.write(self.style.SUCCESS(
            f"✓ {len(GENERAL_AMENITIES)} general + {len(UNIT_AMENITIES)} unit amenities"
        ))
        for name, is_mgmt in PLANS:
            UnitPlan.objects.get_or_create(name=name, defaults={"is_management": is_mgmt})
        self.stdout.write(self.style.SUCCESS(f"✓ {len(PLANS)} unit plans"))
        self.stdout.write(self.style.SUCCESS("Accommodation seed complete."))

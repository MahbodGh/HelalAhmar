from django.core.management.base import BaseCommand

from insurance.models import InsurancePlan

PLANS = [
    {
        "code": "PLAN-BASE", "name": "طرح پایه درمان تکمیلی", "insurer_name": "بیمهٔ ایران",
        "premium_per_person": 1200000, "coverage_ceiling": 200000000, "max_dependents": 6,
        "covered_services": [
            {"name": "بستری و جراحی", "ceiling": 200000000},
            {"name": "پاراکلینیک", "ceiling": 30000000},
            {"name": "دندانپزشکی", "ceiling": 15000000},
        ],
    },
    {
        "code": "PLAN-PLUS", "name": "طرح ویژه درمان تکمیلی", "insurer_name": "بیمهٔ دانا",
        "premium_per_person": 2100000, "coverage_ceiling": 500000000, "max_dependents": 8,
        "covered_services": [
            {"name": "بستری و جراحی", "ceiling": 500000000},
            {"name": "پاراکلینیک", "ceiling": 60000000},
            {"name": "دندانپزشکی", "ceiling": 30000000},
            {"name": "زایمان", "ceiling": 80000000},
        ],
    },
]


class Command(BaseCommand):
    help = "Seed sample supplementary-insurance plans."

    def handle(self, *args, **options):
        created = 0
        for p in PLANS:
            _, was_created = InsurancePlan.objects.update_or_create(code=p["code"], defaults=p)
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"✓ {len(PLANS)} insurance plans ({created} new)"))
        self.stdout.write(self.style.SUCCESS("Insurance seed complete."))

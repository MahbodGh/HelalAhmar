from django.core.management.base import BaseCommand

from referral.models import ContractedProvider

PROVIDERS = [
    {"code": "PRV-CLINIC", "name": "درمانگاه ملت", "category": "medical", "discount_percent": 20},
    {"code": "PRV-PHARM", "name": "داروخانهٔ مرکزی", "category": "pharmacy", "discount_percent": 10},
    {"code": "PRV-GYM", "name": "مجموعهٔ ورزشی آفتاب", "category": "sports", "discount_percent": 30},
    {"code": "PRV-BOOK", "name": "فرهنگسرای کتاب", "category": "cultural", "discount_percent": 15},
]


class Command(BaseCommand):
    help = "Seed sample contracted service providers."

    def handle(self, *args, **options):
        created = 0
        for p in PROVIDERS:
            _, was_created = ContractedProvider.objects.update_or_create(code=p["code"], defaults=p)
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"✓ {len(PROVIDERS)} providers ({created} new)"))
        self.stdout.write(self.style.SUCCESS("Referral seed complete."))

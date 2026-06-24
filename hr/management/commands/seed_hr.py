"""
Seed base HR data: 31 provinces, HQ org unit, and one org unit per province.
Run:  python manage.py seed_hr   (idempotent)
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from hr.models import OrgUnit, Province

PROVINCES = [
    ("آذربایجان شرقی", "P01"), ("آذربایجان غربی", "P02"), ("اردبیل", "P03"),
    ("اصفهان", "P04"), ("البرز", "P05"), ("ایلام", "P06"), ("بوشهر", "P07"),
    ("تهران", "P08"), ("چهارمحال و بختیاری", "P09"), ("خراسان جنوبی", "P10"),
    ("خراسان رضوی", "P11"), ("خراسان شمالی", "P12"), ("خوزستان", "P13"),
    ("زنجان", "P14"), ("سمنان", "P15"), ("سیستان و بلوچستان", "P16"),
    ("فارس", "P17"), ("قزوین", "P18"), ("قم", "P19"), ("کردستان", "P20"),
    ("کرمان", "P21"), ("کرمانشاه", "P22"), ("کهگیلویه و بویراحمد", "P23"),
    ("گلستان", "P24"), ("گیلان", "P25"), ("لرستان", "P26"), ("مازندران", "P27"),
    ("مرکزی", "P28"), ("هرمزگان", "P29"), ("همدان", "P30"), ("یزد", "P31"),
]


class Command(BaseCommand):
    help = "Seed provinces and base organizational structure (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        prov_map = {}
        for name, code in PROVINCES:
            p, _ = Province.objects.update_or_create(code=code, defaults={"name": name})
            prov_map[code] = p
        self.stdout.write(self.style.SUCCESS(f"✓ {len(prov_map)} provinces"))

        hq, _ = OrgUnit.objects.update_or_create(
            code="HQ", defaults={"name": "ستاد مرکزی جمعیت هلال‌احمر", "type": "hq", "parent": None}
        )
        for code, province in prov_map.items():
            OrgUnit.objects.update_or_create(
                code=f"ORG-{code}",
                defaults={
                    "name": f"جمعیت هلال‌احمر استان {province.name}",
                    "type": "province_org", "parent": hq, "province": province,
                },
            )
        self.stdout.write(self.style.SUCCESS(f"✓ HQ + {len(prov_map)} province org units"))
        self.stdout.write(self.style.SUCCESS("HR seed complete."))

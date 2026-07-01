from django.core.management.base import BaseCommand

from loan.models import LoanType

TYPES = [
    {
        "code": "GHARZ", "name": "وام قرض‌الحسنه ضروری", "max_amount": 100_000_000,
        "max_installments": 24, "profit_rate": 0, "fund_budget": 5_000_000_000,
        "allocation_method": LoanType.FCFS,
    },
    {
        "code": "HOUSING", "name": "وام مسکن", "max_amount": 500_000_000,
        "max_installments": 60, "profit_rate": 4, "fund_budget": 20_000_000_000,
        "allocation_method": LoanType.LOTTERY,
    },
]


class Command(BaseCommand):
    help = "Seed sample loan types."

    def handle(self, *args, **options):
        created = 0
        for t in TYPES:
            _, was_created = LoanType.objects.update_or_create(code=t["code"], defaults=t)
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"✓ {len(TYPES)} loan types ({created} new)"))
        self.stdout.write(self.style.SUCCESS("Loan seed complete."))

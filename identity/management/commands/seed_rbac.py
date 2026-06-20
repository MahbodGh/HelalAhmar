"""
Seed RBAC: permission catalog + all RFP roles + super_admin.

Run:  python manage.py seed_rbac
Idempotent — safe to run repeatedly.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from identity.models import Dashboard, Permission, Role

# --- Starter permission catalog (module.entity.action) ---------------------- #
# Extend per module as you build them out.
PERMISSIONS = [
    # identity / admin
    ("identity.role.manage", "مدیریت نقش‌ها و دسترسی‌ها", "identity"),
    ("identity.user.manage", "مدیریت کاربران", "identity"),
    ("identity.audit.view", "مشاهده لاگ‌ها", "identity"),
    # accommodation (نمونه‌ی فاز اول)
    ("accommodation.complex.view", "مشاهده مراکز اقامتی", "accommodation"),
    ("accommodation.complex.manage", "مدیریت مراکز اقامتی", "accommodation"),
    ("accommodation.reservation.create", "ثبت رزرو", "accommodation"),
    ("accommodation.reservation.manage", "مدیریت رزروها", "accommodation"),
    ("accommodation.checkin.manage", "پذیرش و خروج", "accommodation"),
    ("accommodation.housekeeping.manage", "خانه‌داری", "accommodation"),
    ("accommodation.bi.view", "داشبورد BI اقامت", "accommodation"),
    # cross-module welfare
    ("insurance.request.manage", "مدیریت بیمه تکمیلی", "insurance"),
    ("loan.request.manage", "مدیریت وام", "loan"),
    ("referral.letter.manage", "مدیریت معرفی‌نامه", "referral"),
    ("finance.export.view", "خروجی‌های مالی", "finance"),
    ("welfare.profile.view", "مشاهده پروندهٔ رفاهی", "welfare"),
    ("report.dashboard.view", "داشبورد و گزارش‌ها", "report"),
]

# --- Roles from the RFP ----------------------------------------------------- #
# code, display name, is_system, [permission codes | "*" for all]
ROLES = [
    ("super_admin", "مدیر کل سامانه (Super Admin)", True, "*"),
    ("president", "رئیس جمعیت و مدیران ارشد", True, [
        "report.dashboard.view", "welfare.profile.view",
        "accommodation.bi.view", "identity.audit.view",
    ]),
    ("hq_welfare_manager", "مدیر رفاهی ستاد", True, "*"),
    ("hq_accommodation_officer", "مسئول مراکز اقامتی ستاد", True, [
        "accommodation.complex.manage", "accommodation.reservation.manage",
        "accommodation.bi.view", "accommodation.checkin.manage",
    ]),
    ("province_director", "مدیرکل استان", True, [
        "accommodation.complex.view", "accommodation.reservation.manage",
        "accommodation.bi.view", "report.dashboard.view",
    ]),
    ("province_accommodation_officer", "مسئول مراکز اقامتی استان", True, [
        "accommodation.complex.view", "accommodation.reservation.manage",
        "accommodation.checkin.manage",
    ]),
    ("complex_manager", "مدیر مجموعه", True, [
        "accommodation.reservation.manage", "accommodation.checkin.manage",
        "accommodation.housekeeping.manage",
    ]),
    ("complex_executive", "مسئول اجرایی مجموعه", True, [
        "accommodation.reservation.create", "accommodation.checkin.manage",
    ]),
    ("housekeeping", "پرسنل خانه‌داری", True, ["accommodation.housekeeping.manage"]),
    ("province_insurance_expert", "کارشناس بیمه استان", True, ["insurance.request.manage"]),
    ("hq_insurance_expert", "کارشناس بیمه ستاد", True, ["insurance.request.manage"]),
    ("hq_loan_expert", "کارشناس وام ستاد", True, ["loan.request.manage"]),
    ("province_welfare_expert", "کارشناس رفاه استان", True, ["welfare.profile.view"]),
    ("welfare_manager", "مدیر رفاه (استان/کشور)", True, [
        "report.dashboard.view", "welfare.profile.view",
    ]),
    ("finance_unit", "واحد مالی", True, ["finance.export.view"]),
    ("employee", "کارمند / کاربر نهایی", True, [
        "accommodation.reservation.create", "welfare.profile.view",
    ]),
]

# --- Dashboards / menu entries (permission-gated) --------------------------- #
# code, title, icon, route, group, required_permission|None, order
DASHBOARDS = [
    ("overview", "میز کار", "LayoutDashboard", "/dashboard", "عمومی", None, 10),
    ("welfare_profile", "پروندهٔ رفاهی من", "UserRound", "/me/welfare", "عمومی", "welfare.profile.view", 20),
    ("accommodation_centers", "مراکز اقامتی", "Building2", "/accommodation/centers", "اقامت", "accommodation.complex.view", 30),
    ("accommodation_reservations", "رزروها", "CalendarCheck", "/accommodation/reservations", "اقامت", "accommodation.reservation.manage", 40),
    ("accommodation_checkin", "پذیرش و خروج", "ScanLine", "/accommodation/checkin", "اقامت", "accommodation.checkin.manage", 50),
    ("housekeeping", "خانه‌داری", "Sparkles", "/accommodation/housekeeping", "اقامت", "accommodation.housekeeping.manage", 60),
    ("accommodation_bi", "داشبورد اقامت (BI)", "BarChart3", "/accommodation/bi", "اقامت", "accommodation.bi.view", 70),
    ("insurance", "بیمه تکمیلی", "ShieldPlus", "/insurance", "بیمه", "insurance.request.manage", 80),
    ("loan", "وام و تسهیلات", "Banknote", "/loan", "وام", "loan.request.manage", 90),
    ("referral", "معرفی‌نامه‌ها", "FileSignature", "/referral", "خدمات", "referral.letter.manage", 100),
    ("finance", "خروجی‌های مالی", "Wallet", "/finance", "مالی", "finance.export.view", 110),
    ("reports", "گزارش‌ها و داشبورد مدیریتی", "PieChart", "/reports", "گزارش", "report.dashboard.view", 120),
    ("role_management", "مدیریت نقش‌ها و دسترسی‌ها", "KeySquare", "/admin/roles", "مدیریت", "identity.role.manage", 130),
    ("audit_logs", "لاگ‌ها و ممیزی", "ScrollText", "/admin/audit", "مدیریت", "identity.audit.view", 140),
]


class Command(BaseCommand):
    help = "Seed RBAC permissions and RFP roles (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        perm_map = {}
        for code, name, module in PERMISSIONS:
            perm, _ = Permission.objects.update_or_create(
                code=code, defaults={"name": name, "module": module}
            )
            perm_map[code] = perm
        self.stdout.write(self.style.SUCCESS(f"✓ {len(perm_map)} permissions"))

        all_perms = list(perm_map.values())
        for code, name, is_system, perms in ROLES:
            role, _ = Role.objects.update_or_create(
                code=code, defaults={"name": name, "is_system": is_system}
            )
            role.permissions.set(all_perms if perms == "*" else [perm_map[c] for c in perms])
        self.stdout.write(self.style.SUCCESS(f"✓ {len(ROLES)} roles"))

        for code, title, icon, route, group, perm_code, order in DASHBOARDS:
            Dashboard.objects.update_or_create(
                code=code,
                defaults={
                    "title": title, "icon": icon, "route": route, "group": group,
                    "required_permission": perm_map.get(perm_code) if perm_code else None,
                    "order": order, "is_active": True,
                },
            )
        self.stdout.write(self.style.SUCCESS(f"✓ {len(DASHBOARDS)} dashboards"))
        self.stdout.write(self.style.SUCCESS("RBAC seed complete."))

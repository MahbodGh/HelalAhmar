"""
Seed RBAC: permission catalog + all RFP roles + super_admin.

Run:  python manage.py seed_rbac
Idempotent — safe to run repeatedly.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from identity.models import Dashboard, DashboardWidget, Permission, Role

# --- Starter permission catalog (module.entity.action) ---------------------- #
# Extend per module as you build them out.
PERMISSIONS = [
    # identity / admin
    ("identity.role.manage", "مدیریت نقش‌ها و دسترسی‌ها", "identity"),
    ("identity.user.manage", "مدیریت کاربران", "identity"),
    ("identity.audit.view", "مشاهده لاگ‌ها", "identity"),
    # hr / organization
    ("hr.orgunit.view", "مشاهده ساختار سازمانی", "hr"),
    ("hr.orgunit.manage", "مدیریت ساختار سازمانی", "hr"),
    ("hr.personnel.view", "مشاهده پرسنل", "hr"),
    ("hr.personnel.manage", "مدیریت/همگام‌سازی پرسنل", "hr"),
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
        "hr.personnel.view", "hr.orgunit.view",
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
    ("province_welfare_expert", "کارشناس رفاه استان", True, ["welfare.profile.view", "hr.personnel.view"]),
    ("welfare_manager", "مدیر رفاه (استان/کشور)", True, [
        "report.dashboard.view", "welfare.profile.view", "hr.personnel.view",
    ]),
    ("finance_unit", "واحد مالی", True, ["finance.export.view", "hr.personnel.view"]),
    ("employee", "کارمند / کاربر نهایی", True, [
        "accommodation.reservation.create", "welfare.profile.view",
    ]),
]

# --- Dashboards / menu entries (permission-gated) --------------------------- #
# code, title, icon, route, group, required_permission|None, order
DASHBOARDS = [
    ("overview", "میز کار", "LayoutDashboard", "/dashboard", "عمومی", None, 10),
    ("welfare_profile", "پروندهٔ رفاهی من", "UserRound", "/me/welfare", "عمومی", "welfare.profile.view", 20),
    ("hr_personnel", "پرسنل", "Users", "/hr/personnel", "منابع انسانی", "hr.personnel.view", 25),
    ("hr_org_units", "ساختار سازمانی", "Network", "/hr/org-units", "منابع انسانی", "hr.orgunit.view", 26),
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

# --- Dashboard widgets (cards) — gated by permission ------------------------ #
# code, title, type, section, data_key, route, icon, size, permission|None, order, config
WIDGETS = [
    # personal (everyone)
    ("my_welfare_summary", "خلاصهٔ پروندهٔ رفاهی من", "list", "personal", "me.welfare_summary", "/me/welfare", "UserRound", "lg", None, 10, {}),
    ("my_reservations", "رزروهای من", "list", "personal", "me.reservations", "/me/reservations", "CalendarCheck", "md", None, 20, {}),
    ("my_insurance", "بیمهٔ من", "list", "personal", "me.insurance", "/me/insurance", "ShieldPlus", "md", None, 30, {}),
    ("my_loans", "وام‌های من", "list", "personal", "me.loans", "/me/loans", "Banknote", "md", None, 40, {}),
    # quick actions
    ("qa_new_reservation", "رزرو جدید", "quick_action", "quick_actions", "", "/accommodation/reservations/new", "CalendarPlus", "sm", None, 10, {}),
    ("qa_request_insurance", "درخواست بیمه", "quick_action", "quick_actions", "", "/insurance/request", "ShieldPlus", "sm", None, 20, {}),
    ("qa_request_loan", "درخواست وام", "quick_action", "quick_actions", "", "/loan/request", "Banknote", "sm", None, 30, {}),
    ("qa_create_period", "ایجاد دورهٔ رزرو", "quick_action", "quick_actions", "", "/accommodation/periods/new", "CalendarRange", "sm", "accommodation.reservation.manage", 40, {}),
    ("qa_qr_checkin", "پذیرش با QR", "quick_action", "quick_actions", "", "/accommodation/checkin", "ScanLine", "sm", "accommodation.checkin.manage", 50, {}),
    ("qa_walkin", "رزرو حضوری", "quick_action", "quick_actions", "", "/accommodation/walkin", "DoorOpen", "sm", "accommodation.checkin.manage", 60, {}),
    ("qa_insurance_export", "خروجی بیمه", "quick_action", "quick_actions", "", "/insurance/export", "FileDown", "sm", "insurance.request.manage", 70, {}),
    ("qa_loan_lottery", "قرعه‌کشی وام", "quick_action", "quick_actions", "", "/loan/lottery", "Dices", "sm", "loan.request.manage", 80, {}),
    ("qa_finance_export", "خروجی مالی", "quick_action", "quick_actions", "", "/finance/export", "FileDown", "sm", "finance.export.view", 90, {}),
    ("qa_manage_roles", "مدیریت نقش‌ها", "quick_action", "quick_actions", "", "/admin/roles", "KeySquare", "sm", "identity.role.manage", 100, {}),
    # KPIs
    ("kpi_total_personnel", "کل پرسنل", "kpi", "kpis", "hr.total_personnel", "", "Users", "sm", "hr.personnel.view", 5, {}),
    ("kpi_occupancy", "نرخ اشغال", "kpi", "kpis", "accommodation.occupancy_rate", "", "BarChart3", "sm", "accommodation.bi.view", 10, {"unit": "٪"}),
    ("kpi_active_reservations", "رزروهای فعال", "kpi", "kpis", "accommodation.active_reservations", "", "CalendarCheck", "sm", "accommodation.reservation.manage", 20, {}),
    ("kpi_today_checkins", "ورود امروز", "kpi", "kpis", "accommodation.today_checkins", "", "LogIn", "sm", "accommodation.checkin.manage", 30, {}),
    ("kpi_pending_insurance", "بیمهٔ در انتظار بررسی", "kpi", "kpis", "insurance.pending_requests", "", "ShieldAlert", "sm", "insurance.request.manage", 40, {}),
    ("kpi_high_risk", "افراد پرریسک", "kpi", "kpis", "insurance.high_risk_count", "", "ShieldAlert", "sm", "insurance.request.manage", 50, {}),
    ("kpi_pending_loans", "وام‌های در انتظار", "kpi", "kpis", "loan.pending_requests", "", "Banknote", "sm", "loan.request.manage", 60, {}),
    ("kpi_credit_usage", "مصرف اعتبار وام", "kpi", "kpis", "loan.credit_usage", "", "Wallet", "sm", "loan.request.manage", 70, {"unit": "٪"}),
    ("kpi_referrals_issued", "معرفی‌نامه‌های صادرشده", "kpi", "kpis", "referral.issued_count", "", "FileSignature", "sm", "referral.letter.manage", 80, {}),
    ("kpi_monthly_deductions", "کسورات ماه", "kpi", "kpis", "finance.monthly_deductions", "", "Wallet", "sm", "finance.export.view", 90, {}),
    ("kpi_total_services", "کل خدمات توزیع‌شده", "kpi", "kpis", "report.total_services", "", "PieChart", "sm", "report.dashboard.view", 100, {}),
    ("kpi_distribution_fairness", "شاخص عدالت توزیع", "kpi", "kpis", "report.distribution_fairness", "", "Scale", "sm", "report.dashboard.view", 110, {}),
    ("kpi_total_users", "کل کاربران", "kpi", "kpis", "identity.total_users", "", "Users", "sm", "identity.role.manage", 120, {}),
    # charts
    ("chart_reservation_trend", "روند رزرو در فصول", "chart_line", "charts", "accommodation.reservation_trend", "", "TrendingUp", "lg", "accommodation.bi.view", 10, {}),
    ("chart_services_by_province", "توزیع خدمات به تفکیک استان", "chart_bar", "charts", "report.services_by_province", "", "BarChart3", "lg", "report.dashboard.view", 20, {}),
    ("map_province_occupancy", "اشغال به تفکیک استان (نقشه)", "map", "charts", "accommodation.occupancy_by_province", "", "Map", "lg", "accommodation.bi.view", 30, {}),
    # lists / tables
    ("list_popular_centers", "محبوب‌ترین مراکز اقامتی", "list", "lists", "accommodation.popular_centers", "", "Building2", "md", "accommodation.bi.view", 10, {}),
    ("table_unit_status", "وضعیت لحظه‌ای واحدها", "table", "lists", "accommodation.unit_status", "", "LayoutGrid", "lg", "accommodation.checkin.manage", 20, {}),
    ("list_housekeeping_queue", "صف نظافت", "list", "lists", "accommodation.housekeeping_queue", "", "Sparkles", "md", "accommodation.housekeeping.manage", 30, {}),
    ("table_insurance_requests", "درخواست‌های بیمه", "table", "lists", "insurance.requests", "", "ShieldPlus", "lg", "insurance.request.manage", 40, {}),
    ("table_loan_requests", "درخواست‌های وام", "table", "lists", "loan.requests", "", "Banknote", "lg", "loan.request.manage", 50, {}),
    ("table_referrals", "معرفی‌نامه‌های اخیر", "table", "lists", "referral.recent", "", "FileSignature", "md", "referral.letter.manage", 60, {}),
    ("list_critical_missions", "ماموریت‌های بحرانی", "list", "lists", "report.critical_missions", "", "Siren", "md", "report.dashboard.view", 70, {}),
    ("list_finance_exports", "خروجی‌های مالی اخیر", "list", "lists", "finance.exports", "", "FileSpreadsheet", "md", "finance.export.view", 80, {}),
    # admin
    ("table_recent_logins", "آخرین ورودها", "table", "admin", "identity.recent_logins", "/admin/audit", "ScrollText", "lg", "identity.audit.view", 10, {}),
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

        for code, title, wtype, section, data_key, route, icon, size, perm_code, order, config in WIDGETS:
            DashboardWidget.objects.update_or_create(
                code=code,
                defaults={
                    "title": title, "widget_type": wtype, "section": section,
                    "data_key": data_key, "route": route, "icon": icon, "size": size,
                    "config": config,
                    "required_permission": perm_map.get(perm_code) if perm_code else None,
                    "order": order, "is_active": True,
                },
            )
        self.stdout.write(self.style.SUCCESS(f"✓ {len(WIDGETS)} dashboard widgets"))
        self.stdout.write(self.style.SUCCESS("RBAC seed complete."))

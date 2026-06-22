# نیازمندی داشبورد هر نقش — سامانه رفاهیات هلال‌احمر

این سند، نیاز هر نقش از داشبوردش را تعریف می‌کند. پیاده‌سازی به‌صورت **manifest مبتنی بر دسترسی** است:
هر ویجت یک `required_permission` دارد و فقط برای نقشی نمایش داده می‌شود که آن دسترسی را دارد.
پس «داشبورد هر نقش» = مجموعهٔ ویجت‌هایی که با دسترسی‌های آن نقش روشن می‌شوند.

API اصلی: `GET /api/v1/me/dashboard` (ویجت‌ها به تفکیک بخش) و `GET /api/v1/me/dashboard/summary` (مقادیر).

بخش‌های داشبورد: `kpis` (شاخص‌ها) · `quick_actions` (اقدامات سریع) · `charts` (نمودارها) · `lists` (فهرست‌ها/جدول‌ها) · `personal` (پروندهٔ من) · `admin` (مدیریت).
ویجت‌های `personal` برای همهٔ کاربران واردشده نمایش داده می‌شوند.

---

## ۱) super_admin — مدیر کل سامانه
دامنه: کل کشور، همهٔ ماژول‌ها.
- همهٔ ویجت‌ها (دور زدن کامل فیلتر دسترسی).
- KPIها: کل کاربران، و همهٔ شاخص‌های ماژول‌ها.
- مدیریت: آخرین ورودها، مدیریت نقش‌ها.
- اقدامات: همهٔ quick actionها.

## ۲) president — رئیس جمعیت و مدیران ارشد
دامنه: کل کشور، فقط نظارتی/خواندنی.
دسترسی‌ها: report.dashboard.view · accommodation.bi.view · welfare.profile.view · identity.audit.view
- KPIها: کل خدمات توزیع‌شده، شاخص عدالت توزیع، نرخ اشغال کشوری.
- نمودارها: توزیع خدمات به تفکیک استان، روند رزرو، نقشهٔ اشغال استانی.
- فهرست‌ها: ماموریت‌های بحرانی.
- بدون اقدامات عملیاتی (فقط مشاهده).

## ۳) hq_welfare_manager — مدیر رفاهی ستاد
دامنه: کل کشور، کنترل کامل عملیاتی.
دسترسی: `*` (همه) → عملاً همان دامنهٔ super_admin در سطح رفاه.
- همهٔ KPIها، نمودارها، فهرست‌ها و اقدامات سریع همهٔ ماژول‌ها.

## ۴) hq_accommodation_officer — مسئول مراکز اقامتی ستاد
دامنه: اقامت، کل کشور.
دسترسی‌ها: accommodation.complex.manage · accommodation.reservation.manage · accommodation.bi.view · accommodation.checkin.manage
- KPIها: نرخ اشغال، رزروهای فعال، ورود امروز.
- نمودارها: روند رزرو، نقشهٔ اشغال استانی.
- فهرست‌ها: محبوب‌ترین مراکز، وضعیت لحظه‌ای واحدها.
- اقدامات: ایجاد دورهٔ رزرو، پذیرش با QR، رزرو حضوری.

## ۵) province_director — مدیرکل استان
دامنه: استانِ خود.
دسترسی‌ها: accommodation.complex.view · accommodation.reservation.manage · accommodation.bi.view · report.dashboard.view
- KPIها: نرخ اشغال استان، رزروهای فعال، کل خدمات، شاخص عدالت.
- نمودارها: روند رزرو، توزیع خدمات به تفکیک استان، نقشه.
- اقدامات: ایجاد دورهٔ رزرو.

## ۶) province_accommodation_officer — مسئول مراکز اقامتی استان
دامنه: مراکز استانِ خود.
دسترسی‌ها: accommodation.complex.view · accommodation.reservation.manage · accommodation.checkin.manage
- KPIها: رزروهای فعال، ورود امروز.
- فهرست‌ها: وضعیت لحظه‌ای واحدها.
- اقدامات: ایجاد دوره، پذیرش با QR، رزرو حضوری.

## ۷) complex_manager — مدیر مجموعه
دامنه: یک مجموعهٔ اقامتی.
دسترسی‌ها: accommodation.reservation.manage · accommodation.checkin.manage · accommodation.housekeeping.manage
- KPIها: رزروهای فعال، ورود امروز.
- فهرست‌ها: وضعیت لحظه‌ای واحدها، صف نظافت.
- اقدامات: ایجاد دوره، پذیرش با QR، رزرو حضوری.

## ۸) complex_executive — مسئول اجرایی مجموعه (پذیرش)
دامنه: پذیرش یک مجموعه.
دسترسی‌ها: accommodation.reservation.create · accommodation.checkin.manage
- KPIها: ورود امروز.
- فهرست‌ها: وضعیت لحظه‌ای واحدها.
- اقدامات: پذیرش با QR، رزرو حضوری، رزرو جدید.

## ۹) housekeeping — پرسنل خانه‌داری
دامنه: نظافت واحدها.
دسترسی: accommodation.housekeeping.manage
- فهرست‌ها: صف نظافت (واحدهای نیازمند نظافت + ثبت اتمام نظافت).
- (به‌علاوهٔ ویجت‌های شخصی).

## ۱۰) province_insurance_expert — کارشناس بیمه استان
دامنه: بررسی اولیهٔ بیمه در استان.
دسترسی: insurance.request.manage
- KPIها: بیمهٔ در انتظار بررسی، افراد پرریسک.
- فهرست‌ها: درخواست‌های بیمه.
- اقدامات: خروجی بیمه.

## ۱۱) hq_insurance_expert — کارشناس بیمه ستاد
دامنه: تأیید نهایی، قراردادها، تبادل با شرکت بیمه (کل کشور).
دسترسی: insurance.request.manage
- مشابه کارشناس استان + خروجی برای شرکت بیمه و انتقال لیست بیمه‌شدگان (ویجت‌های اقدام).

## ۱۲) hq_loan_expert — کارشناس وام ستاد
دامنه: وام، کل کشور.
دسترسی: loan.request.manage
- KPIها: وام‌های در انتظار، مصرف اعتبار.
- فهرست‌ها: درخواست‌های وام.
- اقدامات: قرعه‌کشی وام.

## ۱۳) province_welfare_expert — کارشناس رفاه استان
دامنه: رفاه استانِ خود.
دسترسی: welfare.profile.view
- پروندهٔ رفاهی پرسنل (دسترسی نمایشی)؛ عمدتاً ویجت‌های شخصی و گزارش‌های سطح استان.

## ۱۴) welfare_manager — مدیر رفاه (استان/کشور)
دامنه: نظارتی.
دسترسی‌ها: report.dashboard.view · welfare.profile.view
- KPIها: کل خدمات، شاخص عدالت توزیع.
- نمودارها: توزیع خدمات به تفکیک استان.
- فهرست‌ها: ماموریت‌های بحرانی.

## ۱۵) finance_unit — واحد مالی
دامنه: مالی.
دسترسی: finance.export.view
- KPIها: کسورات ماه.
- فهرست‌ها: خروجی‌های مالی اخیر.
- اقدامات: خروجی مالی.

## ۱۶) employee — کارمند / کاربر نهایی
دامنه: شخصی.
دسترسی‌ها: accommodation.reservation.create · welfare.profile.view
- بخش شخصی: خلاصهٔ پروندهٔ رفاهی، رزروهای من، بیمهٔ من، وام‌های من.
- اقدامات: رزرو جدید، درخواست بیمه، درخواست وام.

---

## نگاشت ویجت ← دسترسی (مرجع پیاده‌سازی)
| ویجت | بخش | دسترسی موردنیاز | data_key |
|------|-----|------------------|----------|
| نرخ اشغال | kpis | accommodation.bi.view | accommodation.occupancy_rate |
| رزروهای فعال | kpis | accommodation.reservation.manage | accommodation.active_reservations |
| ورود امروز | kpis | accommodation.checkin.manage | accommodation.today_checkins |
| بیمهٔ در انتظار | kpis | insurance.request.manage | insurance.pending_requests |
| افراد پرریسک | kpis | insurance.request.manage | insurance.high_risk_count |
| وام‌های در انتظار | kpis | loan.request.manage | loan.pending_requests |
| مصرف اعتبار وام | kpis | loan.request.manage | loan.credit_usage |
| معرفی‌نامه‌های صادرشده | kpis | referral.letter.manage | referral.issued_count |
| کسورات ماه | kpis | finance.export.view | finance.monthly_deductions |
| کل خدمات | kpis | report.dashboard.view | report.total_services |
| شاخص عدالت توزیع | kpis | report.dashboard.view | report.distribution_fairness |
| کل کاربران | kpis | identity.role.manage | identity.total_users |
| روند رزرو | charts | accommodation.bi.view | accommodation.reservation_trend |
| توزیع خدمات استانی | charts | report.dashboard.view | report.services_by_province |
| نقشهٔ اشغال استانی | charts | accommodation.bi.view | accommodation.occupancy_by_province |
| محبوب‌ترین مراکز | lists | accommodation.bi.view | accommodation.popular_centers |
| وضعیت واحدها | lists | accommodation.checkin.manage | accommodation.unit_status |
| صف نظافت | lists | accommodation.housekeeping.manage | accommodation.housekeeping_queue |
| درخواست‌های بیمه | lists | insurance.request.manage | insurance.requests |
| درخواست‌های وام | lists | loan.request.manage | loan.requests |
| معرفی‌نامه‌های اخیر | lists | referral.letter.manage | referral.recent |
| ماموریت‌های بحرانی | lists | report.dashboard.view | report.critical_missions |
| خروجی‌های مالی | lists | finance.export.view | finance.exports |
| آخرین ورودها | admin | identity.audit.view | identity.recent_logins |
| ویجت‌های «پروندهٔ من» | personal | — (همه) | me.* |

> فقط `identity.*` اکنون مقدار واقعی برمی‌گرداند؛ بقیه تا ساخته‌شدن ماژولشان `status="pending"` دارند.

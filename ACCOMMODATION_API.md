# API ماژول مراکز اقامتی — برش ۱ (زیرساخت پایه) — برای فرانت‌اند

Base URL: `/api/v1`  ·  احراز هویت: `Authorization: Bearer <access>`

دسترسی‌ها: مشاهده `accommodation.complex.view` · مدیریت `accommodation.complex.manage` ·
تغییر وضعیت `accommodation.checkin.manage` یا `complex.manage` · نظافت `accommodation.housekeeping.manage`.
**RLS:** مجموعه‌ها و واحدها بر اساس scope سازمانی کاربر فیلتر می‌شوند (کاربر استان فقط مجموعه‌های همان استان را می‌بیند).

> این برش شامل: امکانات، پلان‌ها، مجموعه‌ها، واحدها، نرخ فصلی، پنل وضعیت واحدها و صف نظافت است.
> رزرو، قرعه‌کشی، ووچر و پذیرش در برش‌های بعدی می‌آیند.

---

## امکانات و پلان‌ها (داده پایه)

### `GET/POST /accommodation/amenities` · `…/{id}` (read: view · write: manage)
```json
{ "id": 1, "name": "اینترنت", "scope": "general", "icon": "Wifi", "is_active": true }
```
`scope`: `general` (مجموعه) یا `unit` (واحد).

### `GET/POST /accommodation/plans` · `…/{id}`
```json
{ "id": 1, "name": "سوئیت", "is_management": false, "description": "" }
```

---

## مجموعه‌های اقامتی

### `GET /accommodation/complexes` — فهرست (صفحه‌بندی، RLS)
پارامترها: `search` · `province` · `is_active=true|false` · `ordering=name` · `page` · `page_size`
```json
{
  "count": 1, "next": null, "previous": null,
  "results": [ { "id": 1, "name": "مهمانسرای ساری", "code": "C-001", "province": 27, "province_name": "مازندران", "city": null, "phone": "011...", "is_active": true, "units_count": 12 } ]
}
```

### `POST /accommodation/complexes` · `GET|PUT|PATCH|DELETE /accommodation/complexes/{id}` (write: manage)
```json
{
  "name": "مهمانسرای ساری", "code": "C-001", "address": "...", "latitude": 36.56, "longitude": 53.06,
  "phone": "011...", "email": "", "org_unit": 28, "province": 27, "city": null,
  "manager": 10, "executive_officer": null, "services_officer": null,
  "housekeeping_staff": [11, 12], "general_amenities": [1, 2, 3], "is_active": true
}
```
> برای کارکرد RLS، `org_unit` مجموعه را حتماً ست کن.

### `GET /accommodation/complexes/{id}/units` — واحدهای مجموعه
### `GET /accommodation/complexes/{id}/plan` — پلان/وضعیت لحظه‌ای (برای نمایش گرافیکی)
```json
{
  "complex": { "id": 1, "name": "مهمانسرای ساری" },
  "status_summary": { "active": 8, "cleaning": 2, "maintenance": 1, "inactive": 1 },
  "units": [ { "id": 5, "name_or_number": "101", "plan_name": "سوئیت", "status": "active", "status_display": "فعال", "standard_capacity": 2, "max_capacity": 4, "is_management": false, "amenities": [4,5] } ]
}
```

---

## واحدهای اقامتی

### `GET /accommodation/units` — فهرست (صفحه‌بندی، RLS)
پارامترها: `search` · `complex` · `status=active|inactive|maintenance|cleaning` · `page` · `page_size`

### `POST /accommodation/units` · `GET|PUT|PATCH|DELETE /accommodation/units/{id}`
```json
{ "complex": 1, "plan": 1, "name_or_number": "101", "standard_capacity": 2, "max_capacity": 4, "area_m2": 45, "amenities": [4,5], "status": "active", "is_management": false }
```

### `POST /accommodation/units/{id}/status` — تغییر وضعیت (checkin.manage یا complex.manage)
```json
{ "status": "maintenance" }
```
مقادیر: `active` · `inactive` · `maintenance` · `cleaning`.

### `POST /accommodation/units/{id}/mark-cleaned` — ثبت اتمام نظافت (وضعیت → فعال)

### `GET/POST /accommodation/units/{id}/rates` — نرخ‌های فصلی واحد
```json
{ "label": "نوروز", "date_from": "1405-01-01", "date_to": "1405-01-13", "price": 850000 }
```
(مبلغ به تومان، نرخ شبانه.)

---

## خانه‌داری

### `GET /accommodation/housekeeping/queue` — صف نظافت (`housekeeping.manage`)
واحدهایی که وضعیتشان «در حال نظافت» است (RLS-اسکوپ). با `mark-cleaned` از صف خارج می‌شوند.

---

## داشبورد
- منوها: «مراکز اقامتی»، و KPIهای جدید **«کل مراکز اقامتی»** و **«واحدهای قابل‌رزرو»** که در `/me/dashboard/summary` مقدار واقعی برمی‌گردانند (`data_key`: `accommodation.total_complexes`, `accommodation.available_units`).
- `accommodation.occupancy_rate` و رزرو-محورها تا برش رزرو همچنان `pending` می‌مانند.

## کدهای وضعیت
`200` · `201` · `204` · `400` · `401` · `403` · `404`.

---

# برش ۲ — دوره‌های رزرو + رزرو FCFS

دسترسی‌ها: مدیریت دوره `accommodation.reservation.manage` · ثبت رزرو `accommodation.reservation.create`.
**مهم:** کاربر باید به یک پرسنل متصل باشد (`User.personnel_id`) تا بتواند برای خودش رزرو کند.

## دوره‌های رزرو

### `GET/POST /accommodation/periods` · `…/{id}` (CRUD: reservation.manage)
بدنهٔ ساخت دوره (FCFS):
```json
{
  "title": "اقامت نوروز ۱۴۰۵", "method": "fcfs", "status": "active",
  "enroll_start": "2026-03-01T00:00:00Z", "enroll_end": "2026-03-15T00:00:00Z",
  "stay_from": "2026-03-20", "stay_to": "2026-04-10",
  "min_nights": 1, "max_nights": 7, "max_total_companions": 3,
  "allowed_capacity_increase": 1, "block_if_used_within_days": 365,
  "price_personnel": 100000, "price_first_degree_companion": 50000, "price_other_companion": 70000,
  "payment_methods": ["online", "payroll"], "payment_deadline_hours": 24,
  "unit_selection_mode": "user",
  "audience_rules": { "employment_type": ["official", "contractual"], "is_retired": false },
  "units": [5, 6, 7]
}
```
`audience_rules` (جامعهٔ هدف، همه اختیاری، خالی = همه): `employment_type` (لیست)، `provinces` (لیست id)، `is_retired` (bool)، `min_service_years` (عدد)، `min_children` (عدد).

### `GET /accommodation/periods/active` — دوره‌های فعالِ قابل‌رزرو برای کاربر جاری (هر کاربر واردشده)
فقط دوره‌هایی که الان در بازهٔ ثبت‌نام‌اند و کاربر مشمولشان است.

### `GET /accommodation/periods/{id}/available-units?check_in=YYYY-MM-DD&check_out=YYYY-MM-DD&persons=N`
واحدهای خالیِ آن دوره برای بازهٔ انتخابی (با لحاظ ظرفیت و عدم‌تداخل). خروجی: فهرست واحدها.

## رزروها

### `POST /accommodation/reservations` — ثبت رزرو (FCFS) (`reservation.create`)
```json
{
  "period": 1, "unit": 5,
  "check_in_date": "2026-03-21", "check_out_date": "2026-03-24",
  "first_degree_companions": 1, "other_companions": 0,
  "payment_method": "online"
}
```
(مدیر با `reservation.manage` می‌تواند فیلد اختیاری `personnel` را برای رزرو سازمانی بفرستد.)

**۲۰۱** → رزرو با `code` یکتا، `total_cost` محاسبه‌شده، `status: "pending_payment"` و `payment_deadline`.
هزینه = تعداد شب × (نرخ پرسنل + همراه‌درجه‌یک×نرخ + سایر×نرخ).

**خطاها:**
- `409` واحد در بازهٔ انتخابی قبلاً رزرو شده (اصل FCFS).
- `400` با `detail` فارسی: خارج از بازهٔ اقامت، تعداد شب نامجاز، ظرفیت ناکافی، عدم اهلیت، روش پرداخت نامجاز، استفادهٔ اخیر، یا عدم اتصال پرسنل.

### `GET /accommodation/reservations` — فهرست (صفحه‌بندی)
کارمند فقط رزروهای خودش را می‌بیند؛ دارندهٔ `reservation.manage` رزروهای محدودهٔ سازمانی خود را (RLS). فیلتر: `status`.

### `GET /accommodation/reservations/{id}` — جزئیات
### `POST /accommodation/reservations/{id}/pay` — پرداخت/تأیید (فعلاً stub؛ درگاه واقعی در برش بعد) → `confirmed`
### `POST /accommodation/reservations/{id}/cancel` — لغو (اگر تأییدشده بود، `is_refunded=true`)

## داشبورد
این برش چند `data_key` را واقعی کرد: `accommodation.active_reservations`، `accommodation.today_checkins`،
و `accommodation.occupancy_rate` (نرخ اشغال امروز = واحدهای اشغال‌شدهٔ تأییدشده ÷ واحدهای فعال).

## نکته
چون مهلت پرداخت داریم، رزروهای پرداخت‌نشده پس از انقضا باید «منقضی» شوند تا ظرفیت آزاد شود.
تابع `expire_overdue()` این کار را می‌کند؛ در محیط واقعی با یک cron/Celery هر چند دقیقه صدا بزن.

---

# برش ۳ — قرعه‌کشی (روش سوم)

برای دوره‌ای با `method: "lottery"`. به‌جای رزرو آنی، کاربران در بازهٔ ثبت‌نام «ثبت‌نام» می‌کنند؛
پس از پایان مهلت، مدیر قرعه‌کشی را اجرا می‌کند و برندگان یک رزرو `pending_payment` می‌گیرند.

## ثبت‌نام (کاربر)

### `POST /accommodation/periods/{id}/enroll` — ثبت‌نام در قرعه‌کشی (`reservation.create`)
```json
{ "first_degree_companions": 1, "other_companions": 0, "preferred_units": [5, 6] }
```
**۲۰۱** → ثبت‌نام با `status: "pending"`. هر پرسنل در هر دوره فقط یک ثبت‌نام دارد (ارسال مجدد آن را به‌روزرسانی می‌کند).
خطاها `400`: دوره قرعه‌کشی نیست، ثبت‌نام باز نیست، عدم اهلیت، همراه بیش از حد، یا عدم اتصال پرسنل.

### `GET /accommodation/periods/{id}/my-enrollment` — وضعیت ثبت‌نام کاربر جاری (`404` اگر ثبت‌نام نکرده)

## قرعه‌کشی (مدیر)

### `POST /accommodation/periods/{id}/run-lottery` — اجرای قرعه‌کشی (`reservation.manage`)
```json
{ "seed": "42" }
```
`seed` اختیاری است (برای بازتولیدپذیری/شفافیت). فقط **پس از پایان مهلت ثبت‌نام** و **یک‌بار** قابل اجراست.
**۲۰۰** →
```json
{ "run_id": 1, "total_enrollments": 120, "winners": 40, "losers": 80 }
```
الگوریتم: انتخاب تصادفیِ وزن‌دار (بر اساس `score` هر ثبت‌نام)، تخصیص واحد به برندگان به‌ترتیب قرعه (با اولویت `preferred_units`)،
رعایت ظرفیت و **سهمیهٔ استانی** (`province_quotas` روی دوره، مثل `{"8": 40}`). هر برنده یک رزرو با مهلت پرداخت می‌گیرد و سپس با `pay` تأیید می‌کند.

### `GET /accommodation/periods/{id}/enrollments` — فهرست ثبت‌نام‌های دوره (`reservation.manage`، RLS)
وضعیت هر ثبت‌نام: `pending` / `won` / `lost` / `cancelled` و در صورت برنده‌شدن `result_reservation`.

## نکته
برندگان مثل رزرو FCFS مهلت پرداخت دارند؛ `expire_overdue()` رزروهای پرداخت‌نشده را آزاد می‌کند.

---

# برش ۴ — ووچر QR + پذیرش (Check-in/Check-out)

این برش چرخهٔ کامل را می‌بندد: پرداخت → صدور خودکار ووچر → اسکن QR در پذیرش → ثبت ورود → ثبت خروج → رفتن خودکار واحد به صف نظافت.

دسترسی پذیرش: `accommodation.checkin.manage` (نقش‌های مسئول اجرایی مجموعه/مسئول اقامت).

## ووچر
هنگام پرداخت (`POST /reservations/{id}/pay`) یک ووچر با توکن یکتا به‌صورت خودکار صادر می‌شود.

### `GET /accommodation/reservations/{id}/voucher` — دریافت ووچر (صاحب رزرو یا مدیر)
```json
{ "token": "x7Kd...", "reservation": 12, "reservation_code": "RSV-000012",
  "issued_at": "2026-06-29T10:00:00Z", "is_active": true, "qr_payload": "HELAL-RSV:x7Kd..." }
```
فرانت `qr_payload` را به یک تصویر QR تبدیل می‌کند (سمت کلاینت). فقط برای رزرو تأییدشده در دسترس است.

## پذیرش (نیازمند `accommodation.checkin.manage`)

### `POST /accommodation/reservations/verify-voucher` — اسکن/استعلام ووچر
```json
{ "token": "x7Kd..." }
```
**۲۰۰** → اطلاعات کامل رزرو (برای نمایش به متصدی پذیرش). `404` اگر ووچر نامعتبر باشد.

### `POST /accommodation/reservations/{id}/check-in` — ثبت ورود
فقط روی رزرو `confirmed`. وضعیت → `checked_in` و `checked_in_at` ثبت می‌شود. اگر تأییدنشده باشد → `400`.

### `POST /accommodation/reservations/{id}/check-out` — ثبت خروج
فقط روی رزرو `checked_in`. وضعیت → `checked_out`، و **واحد به‌صورت خودکار به وضعیت «در حال نظافت» می‌رود** و در `GET /accommodation/housekeeping/queue` ظاهر می‌شود. پرسنل خانه‌داری با `mark-cleaned` آن را به «فعال» برمی‌گرداند.

## چرخهٔ کامل وضعیت رزرو
`pending_payment` → (pay) `confirmed` → (check-in) `checked_in` → (check-out) `checked_out`
(و `cancelled` / `expired` در مسیرهای دیگر).

## نکته
رزروهای `confirmed` و `checked_in` واحد را در بازهٔ اقامت «اشغال» نگه می‌دارند و در محاسبهٔ
عدم‌تداخل و نرخ اشغال لحاظ می‌شوند.

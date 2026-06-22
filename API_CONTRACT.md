# قرارداد API — Identity (نسخهٔ ۱.۱) — برای فرانت‌اند

Base URL (dev): `http://<HOST>:8000/api/v1`
مستندات تعاملی (Swagger): `http://<HOST>:8000/api/docs/`

احراز هویت: **JWT Bearer**. بعد از ورود، در همهٔ درخواست‌های محافظت‌شده این هدر را بفرست:
```
Authorization: Bearer <access_token>
```
نوع محتوا: `application/json`.

---

## جریان کلی برای فرانت

1. کاربر شماره می‌دهد → `POST /auth/otp/request`.
2. کاربر کد را وارد می‌کند → `POST /auth/otp/verify` → دریافت `access` و `refresh` + اطلاعات کاربر.
3. توکن را ذخیره کن و در همهٔ درخواست‌ها بفرست.
4. بعد از ورود، **منو/سایدبار را از `GET /me/dashboards` بساز** و دکمه‌ها را با `GET /me/roles` (آرایهٔ `permissions`) کنترل کن.
5. وقتی `access` منقضی شد (۴۰۱) → با `POST /auth/token/refresh` تازه‌اش کن؛ اگر refresh هم باطل بود → کاربر را به صفحهٔ ورود ببر.

---

## احراز هویت

### `POST /auth/otp/request` — درخواست کد ورود — عمومی
```json
{ "mobile": "09123456789" }
```
**۲۰۰**
```json
{ "detail": "کد ارسال شد.", "expires_in": 120, "request_id": 42 }
```
> کد در پاسخ برنمی‌گردد. در فاز توسعه از پنل ادمین (جدول درخواست‌های OTP) قابل مشاهده است؛ در تولید فقط پیامک می‌شود.

خطاها: `400` موبایل نامعتبر · `429` محدودیت نرخ ( `{ "code": "too_many_requests" }` ).

### `POST /auth/otp/verify` — تأیید کد و دریافت توکن — عمومی
```json
{ "mobile": "09123456789", "code": "123456" }
```
**۲۰۰**
```json
{
  "access": "eyJhbGciOi...",
  "refresh": "eyJhbGciOi...",
  "user": { "id": 1, "mobile": "09123456789", "full_name": "...", "is_super_admin": false }
}
```
خطاها: `400` کد نادرست/منقضی (`invalid_otp`) · `403` کاربر تعریف‌نشده/غیرفعال (`user_not_allowed`).

### `POST /auth/token/refresh` — تمدید access — عمومی
```json
{ "refresh": "eyJhbGciOi..." }
```
**۲۰۰** → `{ "access": "eyJhbGciOi..." }`  (عمر access: ۳۰ دقیقه · refresh: ۷ روز)

---

## کاربر جاری

### `GET /me` — اطلاعات کاربر جاری — نیازمند توکن
```json
{ "id": 1, "mobile": "09123456789", "full_name": "...", "is_super_admin": false }
```

### `GET /me/roles` — نقش‌ها و دسترسی‌ها — نیازمند توکن
```json
{
  "user": { "id": 1, "mobile": "09123456789", "full_name": "...", "is_super_admin": false },
  "is_super_admin": false,
  "roles": [
    { "code": "province_accommodation_officer", "name": "مسئول مراکز اقامتی استان", "scope_org_unit_id": 12 }
  ],
  "permissions": ["accommodation.checkin.manage", "accommodation.complex.view", "accommodation.reservation.manage"]
}
```
> برای show/hide دکمه‌ها و گاردِ مسیرها از آرایهٔ `permissions` استفاده کن. `scope_org_unit_id = null` یعنی سراسری.

### `GET /me/dashboards` — داشبوردهای مجاز کاربر — نیازمند توکن  ⭐
خروجی فقط شامل داشبوردهایی است که کاربر بر اساس دسترسی‌هایش حق دیدن دارد (super admin همه را می‌بیند). برای ساخت سایدبار استفاده کن.
```json
[
  { "code": "overview", "title": "میز کار", "description": "", "icon": "LayoutDashboard", "route": "/dashboard", "group": "عمومی", "required_permission": null, "order": 10 },
  { "code": "accommodation_reservations", "title": "رزروها", "description": "", "icon": "CalendarCheck", "route": "/accommodation/reservations", "group": "اقامت", "required_permission": "accommodation.reservation.manage", "order": 40 }
]
```
فیلدها: `code` شناسهٔ یکتا · `title` عنوان نمایشی · `icon` کلید آیکن (نام lucide) · `route` مسیر فرانت · `group` گروه منو برای دسته‌بندی · `order` ترتیب نمایش. آرایه از قبل بر اساس `order` مرتب است.

### `GET /me/dashboard` — داشبورد خانهٔ کاربر (ویجت‌ها) — نیازمند توکن  ⭐
ویجت‌های هر نقش، گروه‌بندی‌شده در بخش‌ها. با همین یک API داشبورد همهٔ نقش‌ها را بساز (هاردکد لازم نیست).
```json
{
  "user": { "id": 1, "mobile": "09123456789", "full_name": "...", "is_super_admin": false },
  "sections": [
    {
      "key": "kpis",
      "title": "شاخص‌ها",
      "widgets": [
        { "code": "kpi_occupancy", "title": "نرخ اشغال", "type": "kpi", "section": "kpis",
          "data_key": "accommodation.occupancy_rate", "route": null, "icon": "BarChart3",
          "size": "sm", "config": { "unit": "٪" }, "order": 10 }
      ]
    },
    {
      "key": "quick_actions",
      "title": "اقدامات سریع",
      "widgets": [
        { "code": "qa_new_reservation", "title": "رزرو جدید", "type": "quick_action",
          "section": "quick_actions", "data_key": null, "route": "/accommodation/reservations/new",
          "icon": "CalendarPlus", "size": "sm", "config": {}, "order": 10 }
      ]
    }
  ]
}
```
بخش‌ها: `kpis` · `quick_actions` · `charts` · `lists` · `personal` · `admin` (به همین ترتیب).
انواع ویجت (`type`): `kpi`, `chart_line`, `chart_bar`, `chart_pie`, `list`, `table`, `map`, `quick_action`.
رندر بر اساس `type`: KPI کارت عددی، quick_action دکمهٔ لینک به `route`، chart_* نمودار، list/table فهرست/جدول، map نقشه.

### `GET /me/dashboard/summary` — مقادیر ویجت‌ها — نیازمند توکن  ⭐
دیکشنری از `data_key` به مقدار. برای پرکردن کارت‌ها بعد از گرفتن manifest.
```json
{
  "identity.total_users": { "value": 12, "status": "ok", "unit": "کاربر" },
  "accommodation.occupancy_rate": { "value": null, "status": "pending" },
  "loan.pending_requests": { "value": null, "status": "pending" }
}
```
`status: "ok"` یعنی مقدار آماده است؛ `status: "pending"` یعنی ماژول مربوطه هنوز ساخته نشده — کارت را با حالت «به‌زودی»/skeleton نشان بده. با ساخته‌شدن هر ماژول، همان `data_key` مقدار واقعی می‌گیرد بدون تغییر در فرانت.

---

## نقش‌ها و دسترسی‌ها (مدیر کل)

### `GET /roles/` — فهرست همهٔ نقش‌ها — فقط Super Admin
```json
[
  { "id": 1, "code": "super_admin", "name": "مدیر کل سامانه (Super Admin)", "description": "", "is_system": true, "permissions": ["identity.role.manage", "..."] }
]
```
متدهای دیگر روی این منبع (همه فقط Super Admin):
- `POST /roles/` ساخت نقش — بدنه: `{ "code", "name", "description", "permissions": ["<permission_code>", ...] }`
- `GET /roles/{code}` · `PUT/PATCH /roles/{code}` · `DELETE /roles/{code}`

### `GET /permissions` — فهرست همهٔ دسترسی‌ها — فقط Super Admin  ⭐
برای ساخت صفحهٔ «تخصیص دسترسی به نقش». بدون صفحه‌بندی.
```json
[
  { "id": 1, "code": "accommodation.complex.manage", "name": "مدیریت مراکز اقامتی", "module": "accommodation" }
]
```

---

## کدهای وضعیت
| کد | معنی | اقدام فرانت |
|----|------|-------------|
| 200 | موفق | — |
| 400 | ورودی نامعتبر / کد OTP اشتباه | نمایش پیام `detail` |
| 401 | توکن نامعتبر یا منقضی | refresh؛ اگر نشد ← صفحهٔ ورود |
| 403 | عدم دسترسی | مخفی‌کردن/قفل‌کردن قابلیت |
| 429 | محدودیت نرخ OTP | شمارش‌گر و غیرفعال‌کردن موقت دکمه |

---

## فهرست نقش‌های موجود (seed‌شده)
`super_admin`, `president` (رئیس و مدیران ارشد), `hq_welfare_manager` (مدیر رفاهی ستاد),
`hq_accommodation_officer` (مسئول مراکز اقامتی ستاد), `province_director` (مدیرکل استان),
`province_accommodation_officer` (مسئول مراکز اقامتی استان), `complex_manager` (مدیر مجموعه),
`complex_executive` (مسئول اجرایی مجموعه), `housekeeping` (پرسنل خانه‌داری),
`province_insurance_expert`, `hq_insurance_expert` (کارشناسان بیمه),
`hq_loan_expert` (کارشناس وام ستاد), `province_welfare_expert` (کارشناس رفاه استان),
`welfare_manager` (مدیر رفاه), `finance_unit` (واحد مالی), `employee` (کارمند).

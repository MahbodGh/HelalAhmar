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

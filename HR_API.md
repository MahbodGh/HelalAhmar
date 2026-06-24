# API ماژول منابع انسانی و سازمان (hr) — برای فرانت‌اند

Base URL: `/api/v1`  ·  احراز هویت: `Authorization: Bearer <access>`

دسترسی‌ها: مشاهدهٔ پرسنل `hr.personnel.view` · مدیریت/همگام‌سازی `hr.personnel.manage` ·
مشاهدهٔ سازمان `hr.orgunit.view` · مدیریت سازمان `hr.orgunit.manage`.
**نکتهٔ RLS:** فهرست پرسنل بر اساس scope سازمانی کاربر فیلتر می‌شود؛ کاربرِ محدود به یک استان فقط پرسنل زیرمجموعهٔ همان استان را می‌بیند. super_admin و نقش‌های سراسری همه را می‌بینند.

---

## جغرافیا

### `GET /hr/provinces` — فهرست استان‌ها (هر کاربر واردشده) — بدون صفحه‌بندی
```json
[ { "id": 8, "name": "تهران", "code": "P08" } ]
```

### `GET /hr/cities?province=<id>` — فهرست شهرها (اختیاری بر اساس استان)
```json
[ { "id": 1, "name": "...", "code": "", "province": 8 } ]
```

---

## ساختار سازمانی

### `GET /hr/org-units` — فهرست واحدها (`hr.orgunit.view`)
پارامتر: `search`.
```json
[ { "id": 1, "name": "ستاد مرکزی...", "code": "HQ", "type": "hq", "type_display": "ستاد مرکزی", "parent": null, "province": null, "city": null, "is_active": true } ]
```

### `GET /hr/org-units/tree` — درخت سازمانی (تو در تو)
```json
[ { "id": 1, "name": "ستاد مرکزی...", "code": "HQ", "type": "hq", "type_display": "ستاد مرکزی", "province": null,
    "children": [ { "id": 2, "name": "جمعیت هلال‌احمر استان تهران", "code": "ORG-P08", "type": "province_org", "province": 8, "children": [] } ] } ]
```

### `POST /hr/org-units` · `GET|PUT|PATCH|DELETE /hr/org-units/{id}` (`hr.orgunit.manage` برای نوشتن)
```json
{ "name": "اداره رفاه استان تهران", "code": "DEP-TH-01", "type": "department", "parent": 2, "province": 8 }
```

---

## پرسنل

### `GET /hr/personnel` — فهرست (صفحه‌بندی‌شده، RLS-اسکوپ) (`hr.personnel.view`)
پارامترها: `search` (نام/کدملی/شماره پرسنلی) · `org_unit` · `province` · `employment_type` · `employment_status` · `is_retired=true|false` · `gender=m|f` · `ordering` · `page` · `page_size`
```json
{
  "count": 1, "next": null, "previous": null,
  "results": [
    { "id": 10, "national_id": "0012345678", "personnel_no": "8841", "full_name": "مصطفی محدث",
      "employment_type": "official", "employment_status": "active", "is_retired": false,
      "org_unit": 2, "org_unit_name": "جمعیت هلال‌احمر استان تهران", "province": 8, "province_name": "تهران", "job_title": "کارشناس" }
  ]
}
```

### `GET /hr/personnel/{id}` — جزئیات (شامل افراد تحت تکفل و احکام)
```json
{
  "id": 10, "national_id": "0012345678", "personnel_no": "8841",
  "first_name": "مصطفی", "last_name": "محدث", "full_name": "مصطفی محدث",
  "gender": "m", "birth_date": "1370-01-01", "age": 35,
  "employment_type": "official", "employment_status": "active", "hire_date": "1395-06-01",
  "is_retired": false, "org_unit": 2, "province": 8, "job_title": "کارشناس",
  "children_count": 2, "service_years": 9, "computed_service_years": 9,
  "last_synced_at": null,
  "dependents": [ { "id": 1, "relation": "spouse", "relation_display": "همسر", "first_name": "...", "last_name": "...", "national_id": "...", "birth_date": null, "gender": "f", "is_student": false, "notes": "" } ],
  "decrees": [ { "id": 1, "decree_no": "1234", "decree_date": "1402-01-01", "title": "حکم استخدام", "attributes": {}, "effective_from": null, "effective_to": null } ]
}
```

### `POST /hr/personnel` · `PATCH /hr/personnel/{id}` (`hr.personnel.manage`)
کد ملی با الگوریتم رقم کنترلی اعتبارسنجی می‌شود؛ کد ملی نامعتبر → `400`.
> حذف فیزیکی پرسنل وجود ندارد (وضعیت `employment_status` را تغییر بده).

### افراد تحت تکفل
- `GET /hr/personnel/{id}/dependents` — فهرست افراد تحت تکفل
- `POST /hr/personnel/{id}/dependents` — افزودن (بدنه شامل relation/first_name/last_name/national_id/...)
- `PATCH|DELETE /hr/dependents/{id}` — ویرایش/حذف (`hr.personnel.manage`)

### احکام پرسنلی
- `GET /hr/personnel/{id}/decrees` — فهرست احکام

### `POST /hr/personnel/import` — درون‌ریزی/همگام‌سازی انبوه (`hr.personnel.manage`)
جایگزینِ موقتِ اتصال به سامانهٔ منابع انسانی. upsert بر اساس `national_id`.
```json
{ "records": [ { "national_id": "0012345678", "personnel_no": "8841", "first_name": "مصطفی", "last_name": "محدث", "employment_type": "official", "org_unit": 2, "province": 8 } ] }
```
**۲۰۰** → `{ "created": 1, "updated": 0, "total": 1 }`

---

## داشبورد
- منوی جدید: «پرسنل» (`/hr/personnel`) و «ساختار سازمانی» (`/hr/org-units`) در گروه «منابع انسانی».
- ویجت KPI «کل پرسنل» → `data_key = hr.total_personnel` که **همین حالا مقدار واقعی** در `GET /me/dashboard/summary` برمی‌گرداند.

## کدهای وضعیت
`200` · `201` · `204` · `400` (اعتبارسنجی/کدملی) · `401` · `403` · `404`.

# API نقش super_admin — مدیریت کاربران و دسترسی

Base URL: `/api/v1`  ·  احراز هویت: `Authorization: Bearer <access>`
دسترسی موردنیاز: مدیریت کاربران `identity.user.manage` · مدیریت نقش `identity.role.manage` · لاگ‌ها `identity.audit.view`
(super_admin همهٔ این‌ها را دارد.)

این نقش پنل مدیریت سامانه را اداره می‌کند: کاربران، انتساب نقش، نقش‌ها/دسترسی‌ها و لاگ ورود.

---

## مدیریت کاربران

### `GET /admin/users` — فهرست کاربران (صفحه‌بندی‌شده)
پارامترها: `search` (موبایل/نام) · `is_active=true|false` · `ordering=-date_joined|mobile|last_login_at` · `page` · `page_size` (حداکثر ۱۰۰)
```json
{
  "count": 42, "next": "...?page=2", "previous": null,
  "results": [
    {
      "id": 1, "mobile": "09123456789", "full_name": "مصطفی محدث",
      "is_active": true, "is_super_admin": true,
      "date_joined": "2026-06-01T08:00:00Z", "last_login_at": "2026-06-17T06:50:00Z",
      "roles": [ { "id": 5, "role_code": "super_admin", "role_name": "مدیر کل سامانه (Super Admin)", "scope_org_unit_id": null, "is_active": true } ]
    }
  ]
}
```

### `POST /admin/users` — ساخت کاربر
کاربر بدون رمز ساخته می‌شود (ورود فقط با OTP).
```json
{ "mobile": "09120000000", "full_name": "کاربر جدید", "is_active": true }
```
**۲۰۱** → همان شیء کاربر. خطاها: `400` موبایل نامعتبر/تکراری (`{ "mobile": ["..."] }`).

### `GET /admin/users/{id}` — جزئیات کاربر (شامل نقش‌ها)

### `PATCH /admin/users/{id}` — ویرایش کاربر
```json
{ "full_name": "نام جدید", "is_active": false }
```
> حذف فیزیکی کاربر وجود ندارد؛ برای غیرفعال‌کردن `is_active=false` بفرست.

---

## انتساب نقش به کاربر

### `GET /admin/users/{id}/roles` — نقش‌های کاربر
```json
[ { "id": 5, "role_code": "complex_manager", "role_name": "مدیر مجموعه", "scope_org_unit_id": 12, "is_active": true } ]
```

### `POST /admin/users/{id}/roles` — انتساب نقش
```json
{ "role_code": "province_accommodation_officer", "scope_org_unit_id": 12 }
```
`scope_org_unit_id` اختیاری است؛ خالی = دسترسی سراسری.
**۲۰۱** → شیء انتساب نقش. خطا: `400` اگر `role_code` نامعتبر باشد.

### `POST /admin/users/{id}/revoke-role` — حذف یک انتساب نقش
```json
{ "user_role_id": 5 }
```
**۲۰۴** بدون بدنه.

---

## نقش‌ها و دسترسی‌ها

### `GET /roles/` · `POST /roles/` · `GET|PUT|PATCH|DELETE /roles/{code}` — مدیریت نقش‌ها (Super Admin)
بدنهٔ ساخت/ویرایش:
```json
{ "code": "custom_role", "name": "نقش سفارشی", "description": "", "permissions": ["accommodation.complex.view", "report.dashboard.view"] }
```

### `GET /permissions` — کاتالوگ همهٔ دسترسی‌ها (برای صفحهٔ تخصیص دسترسی)
```json
[ { "id": 1, "code": "accommodation.complex.manage", "name": "مدیریت مراکز اقامتی", "module": "accommodation" } ]
```

---

## لاگ ورود

### `GET /admin/audit/logins` — تاریخچهٔ ورود (صفحه‌بندی‌شده)
پارامترها: `search` (موبایل/IP) · `success=true|false` · `page` · `page_size`
```json
{
  "count": 120, "next": "...", "previous": null,
  "results": [
    { "id": 300, "mobile": "09123456789", "success": true, "reason": "ok",
      "ip_address": "85.158.145.83", "user_agent": "Mozilla/5.0 ...",
      "created_at": "2026-06-17T06:50:33Z", "user": 1 }
  ]
}
```

---

## داشبورد این نقش
- `GET /me/dashboard` → super_admin همهٔ ویجت‌ها را می‌بیند (بخش‌های kpis/charts/lists/admin/quick_actions).
- `GET /me/dashboard/summary` → مقادیر؛ `identity.total_users` و `identity.recent_logins` همین حالا مقدار واقعی دارند.

## کدهای وضعیت
`200` موفق · `201` ساخته شد · `204` حذف شد · `400` ورودی نامعتبر · `401` بدون/نامعتبر توکن · `403` بدون دسترسی · `404` یافت نشد.

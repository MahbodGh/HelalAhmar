# قرارداد API — Identity (نسخهٔ ۱) — برای فرانت‌اند

Base URL (dev): `http://127.0.0.1:8000/api/v1`
احراز هویت: **JWT Bearer**. بعد از ورود، در همهٔ درخواست‌های محافظت‌شده هدر زیر را بفرست:

```
Authorization: Bearer <access_token>
```

نوع محتوا: `application/json`. همهٔ پاسخ‌ها JSON هستند.

---

## ۱) درخواست کد ورود
`POST /auth/otp/request` — بدون احراز هویت

**Request**
```json
{ "mobile": "09123456789" }
```

**۲۰۰ OK**
```json
{ "detail": "کد ارسال شد.", "expires_in": 120, "request_id": 42 }
```

**خطاها**
- `400` موبایل نامعتبر → `{ "detail": "شماره موبایل نامعتبر است." }`
- `429` محدودیت نرخ → `{ "detail": "برای ارسال مجدد ۳۰ ثانیه صبر کنید.", "code": "too_many_requests" }`

> در محیط dev، کد در ترمینال سرور چاپ می‌شود (هنوز پیامک واقعی وصل نیست).

---

## ۲) تأیید کد و دریافت توکن
`POST /auth/otp/verify` — بدون احراز هویت

**Request**
```json
{ "mobile": "09123456789", "code": "123456" }
```

**۲۰۰ OK**
```json
{
  "access": "eyJhbGciOi...",
  "refresh": "eyJhbGciOi...",
  "user": {
    "id": 1,
    "mobile": "09123456789",
    "full_name": "مصطفی محدث",
    "is_super_admin": false
  }
}
```

**خطاها**
- `400` کد نادرست/منقضی → `{ "detail": "کد واردشده نادرست است.", "code": "invalid_otp" }`
- `403` کاربر تعریف‌نشده/غیرفعال → `{ "detail": "کاربری با این شماره در سامانه تعریف نشده است.", "code": "user_not_allowed" }`

---

## ۳) تمدید توکن
`POST /auth/token/refresh` — بدون احراز هویت

**Request**
```json
{ "refresh": "eyJhbGciOi..." }
```

**۲۰۰ OK**
```json
{ "access": "eyJhbGciOi..." }
```

(عمر access: ۳۰ دقیقه — refresh: ۷ روز.)

---

## ۴) کاربر جاری
`GET /me` — نیازمند احراز هویت

**۲۰۰ OK**
```json
{ "id": 1, "mobile": "09123456789", "full_name": "مصطفی محدث", "is_super_admin": false }
```

---

## ۵) نقش و دسترسی‌های کاربر جاری  ⭐ (همانی که خواسته بودی)
`GET /me/roles` — نیازمند احراز هویت

**۲۰۰ OK**
```json
{
  "user": { "id": 1, "mobile": "09123456789", "full_name": "مصطفی محدث", "is_super_admin": false },
  "is_super_admin": false,
  "roles": [
    { "code": "province_accommodation_officer", "name": "مسئول مراکز اقامتی استان", "scope_org_unit_id": 12 }
  ],
  "permissions": [
    "accommodation.checkin.manage",
    "accommodation.complex.view",
    "accommodation.reservation.manage"
  ]
}
```

> فرانت می‌تواند منوها/دکمه‌ها را بر اساس آرایهٔ `permissions` نمایش/مخفی کند.
> `scope_org_unit_id = null` یعنی دسترسی سراسری؛ عددی یعنی محدود به آن استان/واحد.

---

## ۶) مدیریت نقش‌ها (فقط Super Admin)
`GET/POST/PUT/DELETE /roles` و `/roles/{code}` — نیازمند نقش super_admin

نمونهٔ آیتم نقش:
```json
{
  "id": 3,
  "code": "hq_welfare_manager",
  "name": "مدیر رفاهی ستاد",
  "description": "",
  "is_system": true,
  "permissions": ["identity.role.manage", "accommodation.complex.manage"]
}
```

> مدیریت کاملِ نقش‌ها، کاربران و انتساب نقش از طریق پنل مدیر کل (`/admin/`) هم در دسترس است.

---

## کدهای وضعیت پرتکرار
| کد | معنی |
|----|------|
| 200 | موفق |
| 400 | ورودی نامعتبر / کد OTP اشتباه |
| 401 | توکن نامعتبر یا منقضی (دوباره لاگین یا refresh) |
| 403 | عدم دسترسی / کاربر مجاز نیست |
| 429 | محدودیت نرخ درخواست OTP |

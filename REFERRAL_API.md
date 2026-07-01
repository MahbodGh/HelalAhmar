# معرفی‌نامهٔ خدمات طرف‌قرارداد — قرارداد API

پایهٔ آدرس‌ها: `/api/v1` — **بدون اسلش انتها**.
مدیریت/صدور: `referral.letter.manage` (کارشناس). ثبت درخواست: هر کاربر واردشدهٔ دارای پرسنل.

## مراکز طرف‌قرارداد

### `GET /referral/providers?active=1&category=medical` — فهرست (هر کاربر واردشده)
دسته‌ها: `medical` (درمانی)، `pharmacy` (دارویی)، `cultural` (فرهنگی)، `sports` (ورزشی)، `educational` (آموزشی)، `tourism` (گردشگری)، `other`.

### `POST/PUT/PATCH/DELETE /referral/providers` · `…/{id}` (نیازمند `referral.letter.manage`)
```json
{ "name": "درمانگاه ملت", "code": "PRV-CLINIC", "category": "medical",
  "province": 8, "city": 120, "address": "...", "phone": "...",
  "discount_percent": 20, "terms": "...", "contract_start": "2026-01-01",
  "contract_end": "2026-12-29", "is_active": true }
```

## معرفی‌نامه‌ها

### `POST /referral/letters` — ثبت درخواست معرفی‌نامه (کارمند)
```json
{ "provider": 3, "service_description": "ویزیت تخصصی", "beneficiary_dependent_id": 12, "note": "..." }
```
- مرکز باید فعال باشد وگرنه `400`.
- `beneficiary_dependent_id` اختیاری (باید از افراد تحت تکفلِ همان پرسنل باشد)؛ خالی = خودِ پرسنل.
- وضعیت اولیه `requested`، کد یکتا `REF-NNNNNN`.
- کارشناس می‌تواند فیلد `personnel` را برای ثبت به‌نمایندگی بفرستد.

### `GET /referral/letters?status=&provider=` — فهرست (صفحه‌بندی، RLS)
کارمند فقط معرفی‌نامه‌های خودش؛ کارشناس محدودهٔ سازمانی خودش.

### `POST /referral/letters/{id}/issue` — صدور (کارشناس)
```json
{ "valid_until": "2026-12-01", "note": "..." }
```
وضعیت → `issued`، `issued_at`/`issued_by`/`valid_until` ثبت می‌شود.

### `POST /referral/letters/{id}/reject` — رد (کارشناس) با `{ "note": "..." }`
### `POST /referral/letters/{id}/mark-used` — ثبت استفاده (کارشناس) → `used`
### `POST /referral/letters/{id}/cancel` — لغو (صاحب؛ در وضعیت requested/issued)

## چرخهٔ وضعیت
`requested` → (issue) `issued` → (mark-used) `used`
&nbsp;&nbsp;&nbsp;&nbsp;↘ (reject) `rejected` / (cancel) `cancelled`

## داشبورد
`referral.issued_count` (تعداد معرفی‌نامه‌های صادرشده/استفاده‌شده، RLS) واقعی شد.
جدول `referral.recent` از `GET /referral/letters` تغذیه می‌شود.

## seed
`python manage.py seed_referral` چهار مرکز نمونه ایجاد می‌کند.

# بیمهٔ تکمیلی — قرارداد API (برش ۱: طرح‌ها + درخواست‌ها)

پایهٔ همهٔ آدرس‌ها: `/api/v1` — **بدون اسلش انتها** (کانونشن کل پروژه).
دسترسی مدیریت/بررسی: `insurance.request.manage` (کارشناس بیمهٔ استان/ستاد).
ثبت درخواست: هر کاربر واردشده که به یک پرسنل متصل باشد (`User.personnel_id`).

## طرح‌های بیمه

### `GET /insurance/plans?active=1` — فهرست طرح‌ها (هر کاربر واردشده)
برای انتخاب طرح هنگام ثبت درخواست. `active=1` فقط طرح‌های فعال.

### `POST/PUT/PATCH/DELETE /insurance/plans` · `…/{id}` (نیازمند `insurance.request.manage`)
```json
{
  "name": "طرح پایه درمان تکمیلی", "code": "PLAN-BASE", "insurer_name": "بیمهٔ ایران",
  "premium_per_person": 1200000, "coverage_ceiling": 200000000,
  "covered_services": [{ "name": "بستری و جراحی", "ceiling": 200000000 }],
  "contract_start": "2026-01-01", "contract_end": "2026-12-29",
  "allow_dependents": true, "max_dependents": 6, "is_active": true
}
```

## درخواست‌های بیمه

### `POST /insurance/requests` — ثبت درخواست (کارمند برای خود)
```json
{ "plan": 1, "dependent_ids": [12, 13], "coverage_start": "2026-01-01", "coverage_end": "2026-12-29" }
```
- `dependent_ids` باید از افراد تحت تکفلِ همان پرسنل باشند، وگرنه `400`.
- حق بیمهٔ کل = `premium_per_person × (۱ + تعداد افراد تحت تکفل)` و خودکار محاسبه می‌شود.
- وضعیت اولیه: `submitted` (در انتظار بررسی). کد یکتا `INS-NNNNNN`.
- کارشناس (`insurance.request.manage`) می‌تواند فیلد اختیاری `personnel` را برای ثبت به‌نمایندگی بفرستد.

### `GET /insurance/requests?status=submitted` — فهرست (صفحه‌بندی، RLS)
کارمند فقط درخواست‌های خودش؛ کارشناس درخواست‌های محدودهٔ سازمانی خودش (بر اساس استان/واحد پرسنلِ متقاضی).

### `GET /insurance/requests/{id}` — جزئیات (شامل `dependents`، `premium_total`، `status`)

### `POST /insurance/requests/{id}/cancel` — لغو (صاحب درخواست؛ فقط draft/submitted)
### `POST /insurance/requests/{id}/approve` — تأیید (کارشناس) با بدنهٔ اختیاری `{ "note": "..." }` → `approved`
### `POST /insurance/requests/{id}/reject` — رد (کارشناس) با `{ "note": "..." }` → `rejected`

## چرخهٔ وضعیت
`submitted` → (approve) `approved` / (reject) `rejected` / (cancel) `cancelled`

## داشبورد
این برش `insurance.pending_requests` (تعداد درخواست‌های در انتظار بررسی، RLS) و
`insurance.high_risk_count` (افراد بیمه‌شدهٔ ۶۰سال‌به‌بالا در درخواست‌های تأییدشده) را واقعی کرد.
جدول‌های `insurance.requests` و `me.insurance` از همین `GET /insurance/requests` تغذیه می‌شوند.

## seed
`python manage.py seed_insurance` دو طرح نمونه (PLAN-BASE، PLAN-PLUS) ایجاد می‌کند.

## نکتهٔ برش بعدی
خسارت/غرامت (claims) و گزارش‌های BI بیمه در برش بعدی اضافه می‌شوند.

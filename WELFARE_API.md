# پروندهٔ رفاهی — قرارداد API

نمای **تجمیعیِ بین‌ماژولی** از تمام خدمات رفاهیِ یک پرسنل (اقامت + بیمه + وام + معرفی‌نامه) به‌علاوهٔ یادداشت‌های کارشناسی.
پایهٔ آدرس‌ها: `/api/v1` — بدون اسلش انتها.

## پروندهٔ من

### `GET /welfare/profile/me` — پروندهٔ رفاهی کاربر جاری (هر کاربرِ دارای پرسنل)
اگر کاربر پرسنلِ متصل نداشته باشد → `400`.
```json
{
  "personnel": { "id": 12, "full_name": "...", "national_id": "...", "personnel_no": "...",
                 "org_unit": 5, "province": 8, "service_years": 14, "age": 41, "dependents_count": 3 },
  "dependents": [ { "id": 1, "full_name": "...", "relation": "فرزند" } ],
  "accommodation": { "total_reservations": 4, "active": 1, "last_stay": "2026-03-20" },
  "insurance": { "active_policies": 1, "total_claims": 6, "approved_claim_total": 42000000 },
  "loans": { "active_loans": 1, "total_approved": 80000000, "monthly_installments": 4000000 },
  "referrals": { "issued": 3, "total": 5 }
}
```
> در نمای شخصی، یادداشت‌های کارشناسی (`notes`) نمایش داده نمی‌شوند.

## پروندهٔ یک پرسنل (کارشناس رفاه)

### `GET /welfare/profile/{personnel_id}` — نیازمند `welfare.profile.view` + هم‌محدودگی سازمانی (RLS)
خارج از محدودهٔ سازمانی → `403`. خروجی مثل بالا، به‌علاوهٔ:
```json
"notes": [ { "id": 3, "category": "flag", "category_display": "هشدار", "text": "...", "created_at": "..." } ]
```

## یادداشت‌های پرونده (کارشناس رفاه: `welfare.profile.view`)

### `GET /welfare/notes?personnel={id}` — فهرست (صفحه‌بندی، RLS)
### `POST /welfare/notes` — افزودن یادداشت
```json
{ "personnel": 12, "category": "flag", "text": "نیازمند رسیدگی ویژه" }
```
`category`: `note` (یادداشت) / `flag` (هشدار) / `priority` (اولویت ویژه). نویسنده خودکار ثبت می‌شود.
### `DELETE /welfare/notes/{id}` — حذف یادداشت

## نکته
این ماژول عمدتاً **فقط‌خواندنی/تجمیعی** است و از مدل‌های ماژول‌های دیگر (اقامت/بیمه/وام/معرفی‌نامه)
به‌صورت lazy می‌خواند؛ با افزوده‌شدن ماژول‌های جدید، خلاصهٔ آن‌ها هم می‌تواند به این پرونده اضافه شود.

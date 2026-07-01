# گزارش‌ها و داشبورد مدیریتی — قرارداد API

لایهٔ **BI مرکزی و فقط‌خواندنی** که ارائهٔ خدمات رفاهی را در همهٔ ماژول‌ها (اقامت + بیمه + وام + معرفی‌نامه)
تجمیع می‌کند، شاخص عدالت توزیع را می‌سنجد و هشدارهای مدیریتی می‌دهد.
همه با دسترسی `report.dashboard.view` و **RLS** (مدیر ستاد: کل کشور؛ مدیر استان: استان خودش). پایه `/api/v1` بدون اسلش انتها.

### `GET /report/summary` — خلاصهٔ مدیریتی
```json
{ "total_services": 1240, "distribution_fairness": 78.5, "provinces_covered": 29, "critical_missions": 3 }
```
- `total_services`: مجموع خدمات ارائه‌شده = رزروهای اقامت + بیمه‌نامه‌های تأییدشده + وام‌های پرداخت‌شده + معرفی‌نامه‌های صادرشده.
- `distribution_fairness` (۰ تا ۱۰۰): هرچه بالاتر، توزیعِ سرانهٔ خدمات بین استان‌ها یکنواخت‌تر است (بر پایهٔ ضریب تغییرات).

### `GET /report/services-by-province` — توزیع خدمات به تفکیک استان (نمودار میله‌ای)
```json
[ { "province_id": 8, "province_name": "تهران", "services": 320, "personnel": 1500, "per_capita": 0.21 }, ... ]
```
مرتب‌شده بر اساس تعداد خدمات (نزولی).

### `GET /report/critical-missions` — ماموریت‌های بحرانی (هشدارها)
```json
[ { "category": "welfare", "title": "پرونده‌های نیازمند رسیدگی ویژه", "count": 12, "severity": "high" },
  { "category": "coverage", "title": "استان‌های بدون خدمت", "count": 2, "severity": "high" } ]
```
هشدارها شامل: خسارت‌ها و وام‌های در انتظار بررسی، پرونده‌های دارای هشدار/اولویت رفاهی، و استان‌های بدون خدمت.

## داشبورد
این ماژول چهار کلید مدیریتی را واقعی کرد (همه RLS-scoped):
`report.total_services`، `report.distribution_fairness`، `report.services_by_province` (نمودار)، و `report.critical_missions` (لیست).
فرانت می‌تواند هم از endpointهای اختصاصی بالا استفاده کند و هم همه را یک‌جا از `/me/dashboard/summary` بگیرد.

## نکته
این ماژول مدل ندارد (کاملاً تجمیعی)؛ با importهای lazy از سایر ماژول‌ها می‌خواند و migration نمی‌خواهد.

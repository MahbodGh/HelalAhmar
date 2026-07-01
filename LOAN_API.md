# وام و تسهیلات — قرارداد API (برش ۱: انواع وام + درخواست‌ها)

پایهٔ آدرس‌ها: `/api/v1` — **بدون اسلش انتها**.
مدیریت/بررسی: `loan.request.manage` (کارشناس وام ستاد). ثبت درخواست: هر کاربرِ دارای پرسنل.

## انواع وام

### `GET /loan/types?active=1` — فهرست انواع وام (هر کاربر واردشده)
### `POST/PUT/PATCH/DELETE /loan/types` · `…/{id}` (نیازمند `loan.request.manage`)
```json
{
  "name": "وام قرض‌الحسنه ضروری", "code": "GHARZ",
  "max_amount": 100000000, "max_installments": 24, "profit_rate": 0,
  "fund_budget": 5000000000, "allocation_method": "fcfs",
  "block_if_active_loan": true,
  "audience_rules": { "min_service_years": 2 }, "is_active": true
}
```
- `profit_rate` درصد کارمزد (۰ = قرض‌الحسنه). `fund_budget` اعتبار کل صندوق (۰ = نامحدود).
- `allocation_method`: `fcfs` / `lottery` / `queue` (قرعه‌کشی در برش بعد).

## درخواست‌های وام

### `POST /loan/requests` — ثبت درخواست (کارمند)
```json
{ "loan_type": 1, "requested_amount": 80000000, "installments_count": 20, "reason": "..." }
```
- اعتبارسنجی: مبلغ `≤ سقف نوع وام`، اقساط `≤ حداکثر اقساط`، اهلیت، و منع داشتن **وام فعال از همان نوع** (اگر `block_if_active_loan`).
- `monthly_installment` خودکار محاسبه می‌شود: `ceil(مبلغ × (۱۰۰+کارمزد)٪ ÷ اقساط)`.
- وضعیت اولیه `submitted`، کد یکتا `LN-NNNNNN`.

### `GET /loan/requests?status=&loan_type=` — فهرست (صفحه‌بندی، RLS)
کارمند فقط درخواست‌های خودش؛ کارشناس محدودهٔ سازمانی خودش.

### `POST /loan/requests/{id}/approve` — تأیید (کارشناس)
```json
{ "approved_amount": 80000000, "note": "..." }
```
اعتبارسنجی: `approved_amount ≤ مبلغ درخواستی` و `≤ اعتبار باقی‌ماندهٔ صندوق` (کنترل **تجمعی** بودجه).
با تأیید، `monthly_installment` بر اساس مبلغ مصوب بازمحاسبه می‌شود. اگر `approved_amount` نفرستی، برابر مبلغ درخواستی فرض می‌شود.

### `POST /loan/requests/{id}/reject` — رد (کارشناس) با `{ "note": "..." }`
### `POST /loan/requests/{id}/disburse` — ثبت پرداخت (کارشناس/مالی) → `disbursed`
### `POST /loan/requests/{id}/cancel` — لغو (صاحب؛ فقط submitted)

## چرخهٔ وضعیت
`submitted` → (approve) `approved` → (disburse) `disbursed` → `settled`
&nbsp;&nbsp;&nbsp;↘ (reject) `rejected` / (cancel) `cancelled`

## داشبورد
- `loan.pending_requests` = تعداد درخواست‌های در انتظار بررسی (RLS).
- `loan.credit_usage` = درصد مصرف اعتبار صندوق = مجموع مبالغ مصوب/پرداخت‌شده ÷ مجموع بودجهٔ انواع وامِ فعال × ۱۰۰.
- جدول `loan.requests` و `me.loans` از `GET /loan/requests` تغذیه می‌شوند.

## seed
`python manage.py seed_loans` دو نوع وام نمونه (GHARZ، HOUSING) ایجاد می‌کند.

## برش بعدی
قرعه‌کشی وام (تخصیص اعتبار محدود بین متقاضیان) و زمان‌بندی اقساط/بازپرداخت.

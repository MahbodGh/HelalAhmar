# بک‌اند سامانه جامع رفاهیات هلال‌احمر — Bounded Context: Identity

اولین Bounded Context: **هویت و دسترسی** (احراز هویت OTP + RBAC + پنل مدیر کل + APIهای فرانت).

## چرا این ساختار DDD؟

DDD «خالص/هگزاگونال» (جداکردن کامل Domain Entity از ORM با Repository و Mapper برای هر مدل) در جنگو
معمولاً منجر به boilerplate سنگین و جنگ با ORM می‌شود. این پروژه **DDD عمل‌گرا / Modular Monolith**
است:

- هر Bounded Context یک اپ جنگو (`identity`, بعداً `accommodation`, `insurance`, ...).
- لایه‌بندی داخل هر context:
  - `domain/` — منطق خالص، بدون جنگو (value objects، قواعد).
  - `application/` — use caseها (orchestration، transaction، قواعد سطح کاربرد). **API فقط این لایه را صدا می‌زند، نه مستقیم ORM را.**
  - `infrastructure/` — آداپتورها (SMS، بعداً درگاه پرداخت، وب‌سرویس HR).
  - `api/` — لایهٔ interface (DRF: serializer، view، permission، url).
  - `models.py` — persistence (ORM). عمداً اینجا ماند تا `makemigrations`/admin بدون دردسر کار کنند.
- `shared/` — Shared Kernel (مدل‌های پایهٔ مشترک مثل `TimeStampedModel`).

## ساختار

```
helal_rafahiyat_backend/
├── config/                 # پروژهٔ جنگو (settings, urls, wsgi/asgi)
├── shared/                 # Shared Kernel
└── identity/               # Bounded Context: هویت و دسترسی
    ├── domain/             # value_objects, services (خالص)
    ├── application/        # services (use caseها)
    ├── infrastructure/     # sms (آداپتور)
    ├── api/                # serializers, permissions, views, urls
    ├── management/commands/seed_rbac.py
    ├── models.py           # User, Role, Permission, UserRole, OtpRequest, LoginAudit
    └── admin.py            # پنل مدیر کل (Super Admin)
```

## راه‌اندازی (قدم‌به‌قدم)

```bash
# 1) محیط مجازی و نصب
python -m venv .venv
source .venv/bin/activate        # ویندوز: .venv\Scripts\activate
pip install -r requirements.txt

# 2) تنظیمات
cp .env.example .env             # در صورت نیاز ویرایش کن

# 3) دیتابیس
python manage.py makemigrations identity
python manage.py migrate

# 4) seed نقش‌ها و دسترسی‌ها (همهٔ نقش‌های RFP + super_admin)
python manage.py seed_rbac

# 5) ساخت مدیر کل (برای ورود به پنل /admin با رمز عبور)
python manage.py createsuperuser   # موبایل + رمز

# 6) اجرا
python manage.py runserver
```

- **پنل مدیر کل (Super Admin):** http://127.0.0.1:8000/admin/ — مدیریت نقش‌ها/دسترسی‌ها، کاربران،
  و مشاهدهٔ **لاگ‌های ورود** (`LoginAudit`) و درخواست‌های OTP. (همان جایی که خواستی لاگین‌ها مشخص باشد.)
- **APIها:** زیر `http://127.0.0.1:8000/api/v1/` — مستندات در `API_CONTRACT.md`.

## جریان ورود OTP

1. کاربر شماره می‌فرستد → `POST /auth/otp/request` → کد یک‌بارمصرف ساخته و «ارسال» می‌شود.
   فعلاً backend پیامک روی `console` است؛ کد را در ترمینال `runserver` می‌بینی.
2. کاربر کد را می‌فرستد → `POST /auth/otp/verify` → اگر درست بود، **JWT (access + refresh)** برمی‌گردد.
3. فرانت با هدر `Authorization: Bearer <access>` بقیهٔ APIها را صدا می‌زند.

> پیش‌فرض امنیتی: فقط کاربرانی که از قبل تعریف شده‌اند می‌توانند وارد شوند
> (`OTP_AUTO_CREATE_USER=False`). برای تست سریع می‌توانی True کنی، یا کاربر را در `/admin` بسازی.

## نکات تولید (RFP §6/§7)

- دیتابیس فعلی sqlite است؛ برای production طبق RFP **SQL Server یا Oracle** (درایور در requirements کامنت شده).
- HTTPS/TLS، OWASP Top 10، گواهی افتا، Penetration Test پیش از تحویل.
- backend پیامک واقعی (کاوه‌نگار/فراز/...) را در `identity/infrastructure/sms.py` اضافه کن، بدون تغییر لایهٔ application.

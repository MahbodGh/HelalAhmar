"""Accommodation application layer — RLS scope resolution + reservations + lottery."""
from __future__ import annotations

import random
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from accommodation.models import (
    AccommodationComplex,
    AccommodationUnit,
    LotteryEnrollment,
    LotteryRun,
    Reservation,
    ReservationPeriod,
)
from hr.models import OrgUnit, Personnel

_SCOPE_PERMS = [
    "accommodation.complex.view", "accommodation.complex.manage",
    "accommodation.reservation.manage", "accommodation.checkin.manage",
    "accommodation.housekeeping.manage", "accommodation.bi.view",
]


def complex_scope_ids(user) -> set[int] | None:
    """Org-unit ids whose complexes the user may see (None = all)."""
    if getattr(user, "is_super_admin", False):
        return None
    from identity.models import UserRole  # lazy

    scopes = (
        UserRole.objects.filter(
            user=user, is_active=True, role__permissions__code__in=_SCOPE_PERMS
        )
        .values_list("scope_org_unit_id", flat=True)
        .distinct()
    )
    allowed: set[int] = set()
    for sid in scopes:
        if sid is None:
            return None
        allowed |= OrgUnit.subtree_ids(sid)
    return allowed


def scoped_complex_qs(user):
    qs = AccommodationComplex.objects.select_related("province", "org_unit", "city").all()
    allowed = complex_scope_ids(user)
    return qs if allowed is None else qs.filter(org_unit_id__in=allowed)


def scoped_unit_qs(user):
    qs = AccommodationUnit.objects.select_related("complex", "plan").all()
    allowed = complex_scope_ids(user)
    return qs if allowed is None else qs.filter(complex__org_unit_id__in=allowed)


# --------------------------------------------------------------------------- #
# Reservations (FCFS)
# --------------------------------------------------------------------------- #
class ReservationError(Exception):
    """Validation/business-rule failure -> HTTP 400."""


class UnitUnavailableError(ReservationError):
    """Unit already booked for the range -> HTTP 409."""


def _user_perms(user) -> set[str]:
    from identity.application.services import get_user_roles
    return set(get_user_roles(user)["permissions"])


def _can_manage(user) -> bool:
    return getattr(user, "is_super_admin", False) or "accommodation.reservation.manage" in _user_perms(user)


def self_personnel(user):
    if not user.personnel_id:
        return None
    return Personnel.objects.filter(id=user.personnel_id).first()


def eligible(personnel, rules: dict) -> bool:
    """Check a personnel against simple target-audience rules (empty = everyone)."""
    if not rules:
        return True
    if "employment_type" in rules and personnel.employment_type not in rules["employment_type"]:
        return False
    if "provinces" in rules and personnel.province_id not in rules["provinces"]:
        return False
    if "is_retired" in rules and bool(personnel.is_retired) != bool(rules["is_retired"]):
        return False
    if "min_service_years" in rules and (personnel.computed_service_years or 0) < rules["min_service_years"]:
        return False
    if "min_children" in rules and personnel.children_count < rules["min_children"]:
        return False
    return True


def _active_holds(unit):
    now = timezone.now()
    return Reservation.objects.filter(unit=unit).filter(
        Q(status__in=[Reservation.CONFIRMED, Reservation.CHECKED_IN])
        | Q(status=Reservation.PENDING_PAYMENT, payment_deadline__gt=now)
    )


def _has_overlap(unit, check_in, check_out, exclude_id=None) -> bool:
    qs = _active_holds(unit).filter(check_in_date__lt=check_out, check_out_date__gt=check_in)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs.exists()


def _fits_capacity(unit, period, persons) -> bool:
    return persons <= unit.max_capacity and persons <= unit.standard_capacity + period.allowed_capacity_increase


def active_periods_for(user):
    now = timezone.now()
    qs = ReservationPeriod.objects.filter(
        status="active", method=ReservationPeriod.METHOD_FCFS,
        enroll_start__lte=now, enroll_end__gte=now,
    ).prefetch_related("units")
    if getattr(user, "is_super_admin", False):
        return list(qs)
    person = self_personnel(user)
    if person is None:
        return list(qs)  # managers without a personnel record still see open periods
    return [p for p in qs if eligible(person, p.audience_rules)]


def available_units(period, check_in, check_out, persons):
    if check_out <= check_in:
        return []
    out = []
    for u in period.units.select_related("complex", "plan").all():
        if u.status != AccommodationUnit.STATUS_ACTIVE:
            continue
        if not _fits_capacity(u, period, persons):
            continue
        if _has_overlap(u, check_in, check_out):
            continue
        out.append(u)
    return out


@transaction.atomic
def create_reservation(*, user, period, unit, check_in, check_out,
                       first_degree=0, other=0, payment_method="", personnel=None):
    # resolve beneficiary (self, or someone else if manager)
    if personnel is not None and not _can_manage(user):
        raise ReservationError("اجازهٔ رزرو برای دیگران را ندارید.")
    beneficiary = personnel or self_personnel(user)
    if beneficiary is None:
        raise ReservationError("به این کاربر پرسنلی متصل نیست.")

    if not period.is_enroll_open:
        raise ReservationError("ثبت‌نام این دوره باز نیست.")
    if not period.units.filter(id=unit.id).exists():
        raise ReservationError("این واحد در این دوره ارائه نشده است.")
    if not eligible(beneficiary, period.audience_rules):
        raise ReservationError("شما مشمول این دوره نیستید.")
    if check_in < period.stay_from or check_out > period.stay_to:
        raise ReservationError("بازهٔ اقامت خارج از بازهٔ مجاز دوره است.")

    nights = (check_out - check_in).days
    if nights < 1:
        raise ReservationError("تاریخ خروج باید بعد از ورود باشد.")
    if nights < period.min_nights or nights > period.max_nights:
        raise ReservationError(f"تعداد شب باید بین {period.min_nights} و {period.max_nights} باشد.")

    companions = first_degree + other
    if companions > period.max_total_companions:
        raise ReservationError("تعداد همراهان بیش از حد مجاز است.")
    persons = 1 + companions
    if not _fits_capacity(unit, period, persons):
        raise ReservationError("ظرفیت واحد برای تعداد نفرات کافی نیست.")

    if payment_method and period.payment_methods and payment_method not in period.payment_methods:
        raise ReservationError("روش پرداخت انتخابی مجاز نیست.")

    if period.block_if_used_within_days:
        cutoff = date.today() - timedelta(days=period.block_if_used_within_days)
        if Reservation.objects.filter(
            personnel=beneficiary, status=Reservation.CONFIRMED, check_out_date__gte=cutoff
        ).exists():
            raise ReservationError("به‌دلیل استفادهٔ اخیر از خدمات اقامتی، امکان رزرو نیست.")

    if _has_overlap(unit, check_in, check_out):
        raise UnitUnavailableError("این واحد در بازهٔ انتخابی قبلاً رزرو شده است.")

    cost = nights * (
        period.price_personnel
        + first_degree * period.price_first_degree_companion
        + other * period.price_other_companion
    )
    res = Reservation.objects.create(
        period=period, unit=unit, personnel=beneficiary, created_by=user,
        check_in_date=check_in, check_out_date=check_out, nights=nights,
        first_degree_companions=first_degree, other_companions=other,
        total_cost=cost, payment_method=payment_method or "",
        status=Reservation.PENDING_PAYMENT,
        payment_deadline=timezone.now() + timedelta(hours=period.payment_deadline_hours),
    )
    res.code = f"RSV-{res.id:06d}"
    res.save(update_fields=["code"])
    return res


@transaction.atomic
def pay_reservation(reservation):
    """Stub for the payment gateway: confirms the reservation and issues a voucher."""
    if reservation.status != Reservation.PENDING_PAYMENT:
        raise ReservationError("این رزرو قابل پرداخت نیست.")
    reservation.status = Reservation.CONFIRMED
    reservation.save(update_fields=["status"])
    issue_voucher(reservation)
    return reservation


# --------------------------------------------------------------------------- #
# Voucher + check-in / check-out (slice 4)
# --------------------------------------------------------------------------- #
def issue_voucher(reservation):
    from accommodation.models import Voucher
    voucher, _ = Voucher.objects.get_or_create(
        reservation=reservation, defaults={"token": Voucher.new_token()}
    )
    return voucher


def find_reservation_by_voucher(token):
    from accommodation.models import Voucher
    v = Voucher.objects.select_related(
        "reservation", "reservation__unit", "reservation__unit__complex", "reservation__personnel"
    ).filter(token=token, is_active=True).first()
    return v.reservation if v else None


@transaction.atomic
def check_in(reservation, user):
    if reservation.status != Reservation.CONFIRMED:
        raise ReservationError("فقط رزرو تأییدشده قابل پذیرش است.")
    reservation.status = Reservation.CHECKED_IN
    reservation.checked_in_at = timezone.now()
    reservation.checked_in_by = user
    reservation.save(update_fields=["status", "checked_in_at", "checked_in_by"])
    return reservation


@transaction.atomic
def check_out(reservation, user):
    if reservation.status != Reservation.CHECKED_IN:
        raise ReservationError("فقط رزرو با وضعیت «ورود انجام‌شده» قابل خروج است.")
    reservation.status = Reservation.CHECKED_OUT
    reservation.checked_out_at = timezone.now()
    reservation.checked_out_by = user
    reservation.save(update_fields=["status", "checked_out_at", "checked_out_by"])
    # feed the housekeeping queue
    unit = reservation.unit
    unit.status = AccommodationUnit.STATUS_CLEANING
    unit.save(update_fields=["status"])
    return reservation


@transaction.atomic
def cancel_reservation(reservation):
    if reservation.status in (Reservation.CANCELLED, Reservation.EXPIRED):
        raise ReservationError("این رزرو قبلاً لغو/منقضی شده است.")
    was_paid = reservation.status == Reservation.CONFIRMED
    reservation.status = Reservation.CANCELLED
    reservation.is_refunded = was_paid
    reservation.save(update_fields=["status", "is_refunded"])
    return reservation


def expire_overdue():
    """Mark pending reservations past their deadline as expired (run periodically)."""
    now = timezone.now()
    return Reservation.objects.filter(
        status=Reservation.PENDING_PAYMENT, payment_deadline__lt=now
    ).update(status=Reservation.EXPIRED)


def scoped_reservations(user):
    qs = Reservation.objects.select_related("period", "unit", "unit__complex", "personnel")
    if getattr(user, "is_super_admin", False):
        return qs
    perms = _user_perms(user)
    scope_perms = (
        "accommodation.reservation.manage",
        "accommodation.checkin.manage",
        "accommodation.bi.view",
    )
    if any(p in perms for p in scope_perms):
        allowed = complex_scope_ids(user)
        return qs if allowed is None else qs.filter(unit__complex__org_unit_id__in=allowed)
    return qs.filter(personnel_id=user.personnel_id) if user.personnel_id else qs.none()


# --------------------------------------------------------------------------- #
# Lottery (method = lottery)
# --------------------------------------------------------------------------- #
class LotteryError(ReservationError):
    """Lottery-specific validation failure -> HTTP 400."""


@transaction.atomic
def enroll_lottery(*, user, period, first_degree=0, other=0, preferred_unit_ids=None, personnel=None):
    if period.method != ReservationPeriod.METHOD_LOTTERY:
        raise LotteryError("این دوره قرعه‌کشی نیست.")
    if not period.is_enroll_open:
        raise LotteryError("ثبت‌نام این دوره باز نیست.")
    if personnel is not None and not _can_manage(user):
        raise LotteryError("اجازهٔ ثبت‌نام برای دیگران را ندارید.")
    beneficiary = personnel or self_personnel(user)
    if beneficiary is None:
        raise LotteryError("به این کاربر پرسنلی متصل نیست.")
    if not eligible(beneficiary, period.audience_rules):
        raise LotteryError("شما مشمول این دوره نیستید.")
    if first_degree + other > period.max_total_companions:
        raise LotteryError("تعداد همراهان بیش از حد مجاز است.")

    enrollment, _ = LotteryEnrollment.objects.update_or_create(
        period=period, personnel=beneficiary,
        defaults={
            "created_by": user,
            "first_degree_companions": first_degree,
            "other_companions": other,
            "status": LotteryEnrollment.PENDING,
        },
    )
    if preferred_unit_ids:
        valid = period.units.filter(id__in=preferred_unit_ids)
        enrollment.preferred_units.set(valid)
    return enrollment


def _pick_unit(units, enrollment, period, persons):
    pref_ids = set(enrollment.preferred_units.values_list("id", flat=True))
    for u in units:
        if u.id in pref_ids and _fits_capacity(u, period, persons):
            return u
    for u in units:
        if _fits_capacity(u, period, persons):
            return u
    return None


@transaction.atomic
def run_lottery(*, period, run_by=None, seed=None):
    if period.method != ReservationPeriod.METHOD_LOTTERY:
        raise LotteryError("این دوره قرعه‌کشی نیست.")
    if timezone.now() < period.enroll_end:
        raise LotteryError("هنوز پایان مهلت ثبت‌نام فرا نرسیده است.")
    if LotteryRun.objects.filter(period=period).exists():
        raise LotteryError("قرعه‌کشی این دوره قبلاً انجام شده است.")

    enrollments = list(
        LotteryEnrollment.objects.filter(period=period, status=LotteryEnrollment.PENDING)
        .select_related("personnel")
        .prefetch_related("preferred_units")
    )
    rng = random.Random(seed)
    # weighted random order (Efraimidis–Spirakis): key = U^(1/weight), pick highest
    ordered = sorted(enrollments, key=lambda e: rng.random() ** (1.0 / max(e.score, 1)), reverse=True)

    units = list(period.units.filter(status=AccommodationUnit.STATUS_ACTIVE).select_related("complex"))
    quotas = {str(k): int(v) for k, v in (period.province_quotas or {}).items()}
    used_by_province: dict = {}
    nights = (period.stay_to - period.stay_from).days or 1
    now = timezone.now()
    winners = 0

    for e in ordered:
        persons = e.persons
        prov = e.personnel.province_id
        if quotas and prov is not None:
            cap = quotas.get(str(prov))
            if cap is not None and used_by_province.get(prov, 0) >= cap:
                e.status = LotteryEnrollment.LOST
                e.save(update_fields=["status"])
                continue
        unit = _pick_unit(units, e, period, persons)
        if unit is None:
            e.status = LotteryEnrollment.LOST
            e.save(update_fields=["status"])
            continue
        units.remove(unit)
        cost = nights * (
            period.price_personnel
            + e.first_degree_companions * period.price_first_degree_companion
            + e.other_companions * period.price_other_companion
        )
        res = Reservation.objects.create(
            period=period, unit=unit, personnel=e.personnel, created_by=run_by,
            check_in_date=period.stay_from, check_out_date=period.stay_to, nights=nights,
            first_degree_companions=e.first_degree_companions, other_companions=e.other_companions,
            total_cost=cost, status=Reservation.PENDING_PAYMENT,
            payment_deadline=now + timedelta(hours=period.payment_deadline_hours),
        )
        res.code = f"RSV-{res.id:06d}"
        res.save(update_fields=["code"])
        e.status = LotteryEnrollment.WON
        e.result_reservation = res
        e.save(update_fields=["status", "result_reservation"])
        used_by_province[prov] = used_by_province.get(prov, 0) + 1
        winners += 1

    run = LotteryRun.objects.create(
        period=period, run_by=run_by, seed="" if seed is None else str(seed),
        total_enrollments=len(enrollments), winners_count=winners,
    )
    period.status = "closed"
    period.save(update_fields=["status"])
    return {
        "run_id": run.id,
        "total_enrollments": len(enrollments),
        "winners": winners,
        "losers": len(enrollments) - winners,
    }


def scoped_enrollments(user, period=None):
    qs = LotteryEnrollment.objects.select_related("personnel", "period", "result_reservation")
    if period is not None:
        qs = qs.filter(period=period)
    if getattr(user, "is_super_admin", False):
        return qs
    if "accommodation.reservation.manage" in _user_perms(user):
        allowed = complex_scope_ids(user)
        if allowed is None:
            return qs
        return qs.filter(period__units__complex__org_unit_id__in=allowed).distinct()
    return qs.filter(personnel_id=user.personnel_id) if user.personnel_id else qs.none()


# --------------------------------------------------------------------------- #
# BI / analytics (slice 5) — all RLS-scoped to the caller
# --------------------------------------------------------------------------- #
def bi_summary(user) -> dict:
    units = scoped_unit_qs(user)
    res = scoped_reservations(user)
    active_units = units.filter(status=AccommodationUnit.STATUS_ACTIVE).count()
    today = date.today()
    occupied = (
        res.filter(status__in=[Reservation.CONFIRMED, Reservation.CHECKED_IN],
                   check_in_date__lte=today, check_out_date__gt=today)
        .values("unit").distinct().count()
    )
    return {
        "total_complexes": scoped_complex_qs(user).filter(is_active=True).count(),
        "total_units": units.count(),
        "available_units": active_units,
        "active_reservations": res.filter(
            status__in=[Reservation.PENDING_PAYMENT, Reservation.CONFIRMED, Reservation.CHECKED_IN]
        ).count(),
        "today_checkins": res.filter(
            check_in_date=today,
            status__in=[Reservation.CONFIRMED, Reservation.CHECKED_IN, Reservation.CHECKED_OUT],
        ).count(),
        "occupancy_rate": round(occupied * 100 / active_units, 1) if active_units else 0,
    }


def bi_reservation_trend(user, months: int = 6) -> list:
    res = scoped_reservations(user).exclude(status=Reservation.CANCELLED)
    rows = (
        res.annotate(m=TruncMonth("check_in_date")).values("m")
        .annotate(count=Count("id")).order_by("m")
    )
    data = [{"month": r["m"].isoformat() if r["m"] else None, "count": r["count"]} for r in rows]
    return data[-months:]


def bi_occupancy_by_province(user) -> list:
    res = scoped_reservations(user).exclude(status=Reservation.CANCELLED)
    rows = (
        res.values("unit__complex__province", "unit__complex__province__name")
        .annotate(reservations=Count("id")).order_by("-reservations")
    )
    return [
        {
            "province_id": r["unit__complex__province"],
            "province_name": r["unit__complex__province__name"],
            "reservations": r["reservations"],
        }
        for r in rows
    ]


def bi_popular_centers(user, limit: int = 10) -> list:
    complexes = (
        scoped_complex_qs(user)
        .annotate(reservations=Count("units__reservations"))
        .order_by("-reservations")[:limit]
    )
    return [{"complex_id": c.id, "name": c.name, "reservations": c.reservations} for c in complexes]


def bi_status_breakdown(user) -> dict:
    units = scoped_unit_qs(user)
    res = scoped_reservations(user)
    unit_status = {r["status"]: r["c"] for r in units.values("status").annotate(c=Count("id"))}
    res_status = {r["status"]: r["c"] for r in res.values("status").annotate(c=Count("id"))}
    return {"units": unit_status, "reservations": res_status}


def resolve_stat(key: str, user) -> dict:
    """Resolve an accommodation.* dashboard data_key to a scoped value."""
    today = date.today()
    if key == "accommodation.total_complexes":
        return {"value": scoped_complex_qs(user).filter(is_active=True).count(), "status": "ok", "unit": "مرکز"}
    if key == "accommodation.available_units":
        return {"value": scoped_unit_qs(user).filter(status=AccommodationUnit.STATUS_ACTIVE).count(), "status": "ok", "unit": "واحد"}
    if key == "accommodation.active_reservations":
        n = scoped_reservations(user).filter(
            status__in=[Reservation.PENDING_PAYMENT, Reservation.CONFIRMED, Reservation.CHECKED_IN]
        ).count()
        return {"value": n, "status": "ok", "unit": "رزرو"}
    if key == "accommodation.today_checkins":
        n = scoped_reservations(user).filter(
            check_in_date=today,
            status__in=[Reservation.CONFIRMED, Reservation.CHECKED_IN, Reservation.CHECKED_OUT],
        ).count()
        return {"value": n, "status": "ok", "unit": "ورود"}
    if key == "accommodation.occupancy_rate":
        return {"value": bi_summary(user)["occupancy_rate"], "status": "ok", "unit": "٪"}
    if key == "accommodation.reservation_trend":
        return {"value": bi_reservation_trend(user), "status": "ok"}
    if key == "accommodation.occupancy_by_province":
        return {"value": bi_occupancy_by_province(user), "status": "ok"}
    if key == "accommodation.popular_centers":
        return {"value": bi_popular_centers(user), "status": "ok"}
    if key == "accommodation.unit_status":
        return {"value": bi_status_breakdown(user)["units"], "status": "ok"}
    if key == "accommodation.housekeeping_queue":
        return {"value": scoped_unit_qs(user).filter(status=AccommodationUnit.STATUS_CLEANING).count(), "status": "ok", "unit": "واحد"}
    return {"value": None, "status": "pending"}

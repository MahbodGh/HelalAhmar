"""Central reporting/BI layer — aggregates welfare-service delivery across all
modules (accommodation, insurance, loan, referral, welfare) with a fairness
index and critical alerts. Read-only; RLS-scoped by report.dashboard.view.
"""
from __future__ import annotations

from collections import defaultdict

from django.db.models import Count

from hr.models import OrgUnit, Personnel, Province

VIEW = "report.dashboard.view"


def _user_perms(user) -> set[str]:
    from identity.application.services import get_user_roles
    return set(get_user_roles(user)["permissions"])


def scope_org_ids(user) -> set[int] | None:
    """Org-unit subtree a manager may report on (None = whole country)."""
    if getattr(user, "is_super_admin", False):
        return None
    from identity.models import UserRole

    scopes = (
        UserRole.objects.filter(user=user, is_active=True, role__permissions__code=VIEW)
        .values_list("scope_org_unit_id", flat=True)
        .distinct()
    )
    allowed: set[int] = set()
    for sid in scopes:
        if sid is None:
            return None
        allowed |= OrgUnit.subtree_ids(sid)
    return allowed


def _scoped(qs, org_ids, field="personnel__org_unit_id"):
    return qs if org_ids is None else qs.filter(**{f"{field}__in": org_ids})


# --------------------------------------------------------------------------- #
# Per-province service counts across modules
# --------------------------------------------------------------------------- #
def _province_counts(qs, org_ids, field="personnel__org_unit_id") -> dict[int, int]:
    rows = (
        _scoped(qs, org_ids, field)
        .values("personnel__province_id")
        .annotate(c=Count("id"))
    )
    return {r["personnel__province_id"]: r["c"] for r in rows if r["personnel__province_id"]}


def _merge(into: dict[int, int], src: dict[int, int]) -> None:
    for k, v in src.items():
        into[k] += v


def province_service_map(user) -> dict[int, int]:
    org_ids = scope_org_ids(user)
    from accommodation.models import Reservation
    from insurance.models import InsuranceRequest
    from loan.models import LoanRequest
    from referral.models import ReferralLetter

    totals: dict[int, int] = defaultdict(int)
    _merge(totals, _province_counts(
        Reservation.objects.filter(status__in=[Reservation.CONFIRMED, Reservation.CHECKED_IN, Reservation.CHECKED_OUT]),
        org_ids,
    ))
    _merge(totals, _province_counts(InsuranceRequest.objects.filter(status=InsuranceRequest.APPROVED), org_ids))
    _merge(totals, _province_counts(LoanRequest.objects.filter(status__in=[LoanRequest.DISBURSED, LoanRequest.SETTLED]), org_ids))
    _merge(totals, _province_counts(ReferralLetter.objects.filter(status__in=[ReferralLetter.ISSUED, ReferralLetter.USED]), org_ids))
    return dict(totals)


def total_services(user) -> int:
    return sum(province_service_map(user).values())


def services_by_province(user) -> list[dict]:
    org_ids = scope_org_ids(user)
    svc = province_service_map(user)
    pers = _scoped(Personnel.objects.all(), org_ids, "org_unit_id").values("province_id").annotate(c=Count("id"))
    pers_map = {r["province_id"]: r["c"] for r in pers if r["province_id"]}

    province_ids = set(svc) | set(pers_map)
    names = {p.id: p.name for p in Province.objects.filter(id__in=province_ids)}
    out = []
    for pid in province_ids:
        personnel = pers_map.get(pid, 0)
        services = svc.get(pid, 0)
        out.append({
            "province_id": pid,
            "province_name": names.get(pid, "—"),
            "services": services,
            "personnel": personnel,
            "per_capita": round(services / personnel, 2) if personnel else 0,
        })
    out.sort(key=lambda r: r["services"], reverse=True)
    return out


def distribution_fairness(user) -> float:
    """0–100; higher = services spread more evenly across provinces (per-capita)."""
    rows = [r for r in services_by_province(user) if r["personnel"] > 0]
    pcs = [r["per_capita"] for r in rows]
    if len(pcs) < 2:
        return 100.0
    mean = sum(pcs) / len(pcs)
    if mean == 0:
        return 100.0
    var = sum((x - mean) ** 2 for x in pcs) / len(pcs)
    cv = (var ** 0.5) / mean
    return round(max(0.0, min(100.0, 100 * (1 - cv))), 1)


def critical_missions(user) -> list[dict]:
    org_ids = scope_org_ids(user)
    from insurance.models import InsuranceClaim
    from loan.models import LoanRequest
    from welfare.models import WelfareNote

    alerts = []
    pending_claims = _scoped(InsuranceClaim.objects.filter(status=InsuranceClaim.SUBMITTED), org_ids).count()
    if pending_claims:
        alerts.append({"category": "insurance", "title": "خسارت‌های در انتظار بررسی", "count": pending_claims, "severity": "medium"})
    pending_loans = _scoped(LoanRequest.objects.filter(status=LoanRequest.SUBMITTED), org_ids).count()
    if pending_loans:
        alerts.append({"category": "loan", "title": "وام‌های در انتظار بررسی", "count": pending_loans, "severity": "medium"})
    flags = _scoped(WelfareNote.objects.filter(category__in=[WelfareNote.FLAG, WelfareNote.PRIORITY]), org_ids).count()
    if flags:
        alerts.append({"category": "welfare", "title": "پرونده‌های نیازمند رسیدگی ویژه", "count": flags, "severity": "high"})
    underserved = [r for r in services_by_province(user) if r["personnel"] > 0 and r["services"] == 0]
    if underserved:
        alerts.append({"category": "coverage", "title": "استان‌های بدون خدمت", "count": len(underserved), "severity": "high"})
    return alerts


def summary(user) -> dict:
    rows = services_by_province(user)
    return {
        "total_services": sum(r["services"] for r in rows),
        "distribution_fairness": distribution_fairness(user),
        "provinces_covered": sum(1 for r in rows if r["services"] > 0),
        "critical_missions": len(critical_missions(user)),
    }


def resolve_stat(key: str, user) -> dict:
    if key == "report.total_services":
        return {"value": total_services(user), "status": "ok", "unit": "خدمت"}
    if key == "report.distribution_fairness":
        return {"value": distribution_fairness(user), "status": "ok", "unit": "٪"}
    if key == "report.services_by_province":
        return {"value": services_by_province(user), "status": "ok"}
    if key == "report.critical_missions":
        return {"value": critical_missions(user), "status": "ok"}
    return {"value": None, "status": "pending"}

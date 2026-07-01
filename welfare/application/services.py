"""Welfare profile — a cross-module read-only consolidation of a personnel's
welfare services (accommodation, insurance, loans, referrals) + staff notes.
"""
from __future__ import annotations

from django.db.models import Sum

from hr.models import OrgUnit, Personnel
from welfare.models import WelfareNote

VIEW = "welfare.profile.view"


class WelfareError(Exception):
    pass


def _user_perms(user) -> set[str]:
    from identity.application.services import get_user_roles
    return set(get_user_roles(user)["permissions"])


def _can_view_others(user) -> bool:
    return getattr(user, "is_super_admin", False) or VIEW in _user_perms(user)


def profile_scope_org_ids(user) -> set[int] | None:
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


def can_view_personnel(user, personnel) -> bool:
    if personnel.id == user.personnel_id:
        return True
    if not _can_view_others(user):
        return False
    allowed = profile_scope_org_ids(user)
    return allowed is None or personnel.org_unit_id in allowed


def scoped_notes(user):
    qs = WelfareNote.objects.select_related("personnel", "author")
    if getattr(user, "is_super_admin", False):
        return qs
    if VIEW in _user_perms(user):
        allowed = profile_scope_org_ids(user)
        return qs if allowed is None else qs.filter(personnel__org_unit_id__in=allowed)
    return qs.none()


# --------------------------------------------------------------------------- #
# Cross-module aggregation
# --------------------------------------------------------------------------- #
def _accommodation_summary(personnel) -> dict:
    from accommodation.models import Reservation
    rs = Reservation.objects.filter(personnel=personnel)
    last = rs.filter(status__in=[Reservation.CHECKED_OUT, Reservation.CHECKED_IN]).order_by("-check_in_date").first()
    return {
        "total_reservations": rs.count(),
        "active": rs.filter(status__in=[Reservation.CONFIRMED, Reservation.CHECKED_IN]).count(),
        "last_stay": last.check_in_date.isoformat() if last else None,
    }


def _insurance_summary(personnel) -> dict:
    from insurance.models import InsuranceClaim, InsuranceRequest
    reqs = InsuranceRequest.objects.filter(personnel=personnel)
    claims = InsuranceClaim.objects.filter(personnel=personnel)
    approved_total = claims.filter(
        status__in=[InsuranceClaim.APPROVED, InsuranceClaim.PAID]
    ).aggregate(s=Sum("approved_amount"))["s"] or 0
    return {
        "active_policies": reqs.filter(status=InsuranceRequest.APPROVED).count(),
        "total_claims": claims.count(),
        "approved_claim_total": approved_total,
    }


def _loan_summary(personnel) -> dict:
    from loan.models import LoanRequest
    reqs = LoanRequest.objects.filter(personnel=personnel)
    active = reqs.filter(status__in=[LoanRequest.APPROVED, LoanRequest.DISBURSED])
    return {
        "active_loans": active.count(),
        "total_approved": active.aggregate(s=Sum("approved_amount"))["s"] or 0,
        "monthly_installments": active.aggregate(s=Sum("monthly_installment"))["s"] or 0,
    }


def _referral_summary(personnel) -> dict:
    from referral.models import ReferralLetter
    ls = ReferralLetter.objects.filter(personnel=personnel)
    return {
        "issued": ls.filter(status__in=[ReferralLetter.ISSUED, ReferralLetter.USED]).count(),
        "total": ls.count(),
    }


def build_profile(personnel, include_notes=False) -> dict:
    data = {
        "personnel": {
            "id": personnel.id,
            "full_name": personnel.full_name,
            "national_id": personnel.national_id,
            "personnel_no": personnel.personnel_no,
            "org_unit": personnel.org_unit_id,
            "province": personnel.province_id,
            "service_years": personnel.computed_service_years,
            "age": personnel.age,
            "dependents_count": personnel.dependents.count(),
        },
        "dependents": [
            {"id": d.id, "full_name": d.full_name, "relation": d.get_relation_display()}
            for d in personnel.dependents.all()
        ],
        "accommodation": _accommodation_summary(personnel),
        "insurance": _insurance_summary(personnel),
        "loans": _loan_summary(personnel),
        "referrals": _referral_summary(personnel),
    }
    if include_notes:
        data["notes"] = [
            {
                "id": n.id, "category": n.category, "category_display": n.get_category_display(),
                "text": n.text, "created_at": n.created_at.isoformat(),
            }
            for n in personnel.welfare_notes.all()
        ]
    return data

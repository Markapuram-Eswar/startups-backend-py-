"""CamelCase view of Startup row — matches Prisma JSON shape for field access."""

from __future__ import annotations

from datetime import datetime

from app.models import Founder, Funding, Startup


def _dt_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat() + ("Z" if dt.tzinfo is None else "")


def founder_to_camel(f: Founder) -> dict:
    return {
        "id": f.id,
        "startupId": f.startup_id,
        "fullName": f.full_name,
        "email": f.email,
        "phone1": f.phone1,
        "phone2": f.phone2,
        "linkedin": f.linkedin,
        "education": f.education,
        "womanFounder": f.woman_founder,
        "scstFounder": f.scst_founder,
    }


def funding_to_camel(fr: Funding) -> dict:
    return {
        "id": fr.id,
        "startupId": fr.startup_id,
        "source": fr.source,
        "type": fr.fund_type,
        "amount": fr.amount,
        "date": _dt_iso(fr.date),
    }


def startup_scalars_camel(s: Startup) -> dict:
    """Full scalar fields for API responses."""
    return {
        "id": s.id,
        "isApproved": s.is_approved,
        "status": s.status.value,
        "rejectionReason": s.rejection_reason,
        "createdById": s.created_by_id,
        "name": s.name,
        "logo": s.logo,
        "documents": s.documents,
        "website": s.website,
        "industry": s.industry,
        "startupDescription": s.startup_description,
        "productDescription": s.product_description,
        "stage": s.stage,
        "trl": s.trl,
        "incorporationDate": _dt_iso(s.incorporation_date),
        "roc": s.roc,
        "cin": s.cin,
        "companyEstablishedYear": s.company_established_year,
        "locations": list(s.locations or []),
        "coreTechnology": s.core_technology,
        "ipStatus": s.ip_status,
        "ipTitle": s.ip_title,
        "ipFilingDate": _dt_iso(s.ip_filing_date),
        "ipCurrentStatus": s.ip_current_status,
        "roadmap": s.roadmap,
        "revenueFY25_26": s.revenue_fy25_26,
        "revenueFY24_25": s.revenue_fy24_25,
        "revenueFY23_24": s.revenue_fy23_24,
        "revenueFY22_23": s.revenue_fy22_23,
        "revenueFY21_22": s.revenue_fy21_22,
        "valuation": s.valuation,
        "captable": s.captable,
        "jobsFullTime": s.jobs_full_time,
        "jobsPartTime": s.jobs_part_time,
        "achievements": s.achievements,
        "incubationJoinDate": _dt_iso(s.incubation_join_date),
        "supportProvided": s.support_provided,
        "supportFunding": s.support_funding,
        "supportOfficeSpace": s.support_office_space,
        "supportIndustryConnects": s.support_industry_connects,
        "supportInvestorConnects": s.support_investor_connects,
        "fundingProvided": s.funding_provided,
        "milestonesCommitted": s.milestones_committed,
        "milestonesAchieved": s.milestones_achieved,
        "dismissedActivityKeys": list(s.dismissed_activity_keys or []),
        "createdAt": _dt_iso(s.created_at),
        "updatedAt": _dt_iso(s.updated_at),
    }


def startup_row_camel(s: Startup) -> dict:
    """Flat camelCase fields for dynamic admin fieldKey resolution."""
    return {
        "name": s.name,
        "logo": s.logo,
        "website": s.website,
        "industry": s.industry,
        "startupDescription": s.startup_description,
        "productDescription": s.product_description,
        "stage": s.stage,
        "trl": s.trl,
        "incorporationDate": _dt_iso(s.incorporation_date),
        "roc": s.roc,
        "cin": s.cin,
        "companyEstablishedYear": s.company_established_year,
        "locations": list(s.locations or []),
        "coreTechnology": s.core_technology,
        "ipStatus": s.ip_status,
        "ipTitle": s.ip_title,
        "ipFilingDate": _dt_iso(s.ip_filing_date),
        "ipCurrentStatus": s.ip_current_status,
        "roadmap": s.roadmap,
        "revenueFY25_26": s.revenue_fy25_26,
        "revenueFY24_25": s.revenue_fy24_25,
        "revenueFY23_24": s.revenue_fy23_24,
        "revenueFY22_23": s.revenue_fy22_23,
        "revenueFY21_22": s.revenue_fy21_22,
        "valuation": s.valuation,
        "captable": s.captable,
        "jobsFullTime": s.jobs_full_time,
        "jobsPartTime": s.jobs_part_time,
        "achievements": s.achievements,
        "incubationJoinDate": _dt_iso(s.incubation_join_date),
        "supportProvided": s.support_provided,
        "supportFunding": s.support_funding,
        "supportOfficeSpace": s.support_office_space,
        "supportIndustryConnects": s.support_industry_connects,
        "supportInvestorConnects": s.support_investor_connects,
        "fundingProvided": s.funding_provided,
        "milestonesCommitted": s.milestones_committed,
        "milestonesAchieved": s.milestones_achieved,
        "isApproved": s.is_approved,
        "status": s.status.value,
        "rejectionReason": s.rejection_reason,
    }

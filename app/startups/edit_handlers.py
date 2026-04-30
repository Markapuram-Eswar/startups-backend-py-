"""Admin inline field edit — mirrors startupController addEditHistory."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.mail_out import send_email_with_template
from app.models import EditHistory, Founder, Funding, Notification, Startup, StartupStatus, User
from app.startups.utils import safe_date, to_bool, to_num
from app.util_ids import new_cuid

FOUNDER_CHILD = {
    "fullName": "full_name",
    "email": "email",
    "phone1": "phone1",
    "phone2": "phone2",
    "linkedin": "linkedin",
    "education": "education",
    "womanFounder": "woman_founder",
    "scstFounder": "scst_founder",
}
FUNDING_CHILD = {
    "source": "source",
    "type": "fund_type",
    "amount": "amount",
    "date": "date",
}

TOP_LEVEL = {
    "name": ("name", "str"),
    "logo": ("logo", "str"),
    "website": ("website", "str"),
    "industry": ("industry", "str"),
    "startupDescription": ("startup_description", "str"),
    "productDescription": ("product_description", "str"),
    "stage": ("stage", "str"),
    "trl": ("trl", "str"),
    "incorporationDate": ("incorporation_date", "date"),
    "roc": ("roc", "str"),
    "cin": ("cin", "str"),
    "companyEstablishedYear": ("company_established_year", "int"),
    "locations": ("locations", "str_list"),
    "coreTechnology": ("core_technology", "str"),
    "ipStatus": ("ip_status", "str"),
    "ipTitle": ("ip_title", "str"),
    "ipFilingDate": ("ip_filing_date", "date"),
    "ipCurrentStatus": ("ip_current_status", "str"),
    "roadmap": ("roadmap", "str"),
    "revenueFY25_26": ("revenue_fy25_26", "float"),
    "revenueFY24_25": ("revenue_fy24_25", "float"),
    "revenueFY23_24": ("revenue_fy23_24", "float"),
    "revenueFY22_23": ("revenue_fy22_23", "float"),
    "revenueFY21_22": ("revenue_fy21_22", "float"),
    "valuation": ("valuation", "float"),
    "captable": ("captable", "str"),
    "jobsFullTime": ("jobs_full_time", "int"),
    "jobsPartTime": ("jobs_part_time", "int"),
    "achievements": ("achievements", "str"),
    "incubationJoinDate": ("incubation_join_date", "date"),
    "supportProvided": ("support_provided", "str"),
    "supportFunding": ("support_funding", "bool"),
    "supportOfficeSpace": ("support_office_space", "bool"),
    "supportIndustryConnects": ("support_industry_connects", "bool"),
    "supportInvestorConnects": ("support_investor_connects", "bool"),
    "fundingProvided": ("funding_provided", "float"),
    "milestonesCommitted": ("milestones_committed", "str"),
    "milestonesAchieved": ("milestones_achieved", "str"),
    "isApproved": ("is_approved", "bool"),
    "status": ("status", "enum"),
    "rejectionReason": ("rejection_reason", "str"),
}


def _parse_value(field_key: str, new_value: Any, kind: str, old_raw: Any) -> Any:
    if (
        kind == "bool"
        or field_key
        in (
            "supportFunding",
            "supportOfficeSpace",
            "supportIndustryConnects",
            "supportInvestorConnects",
            "isApproved",
        )
        or field_key.endswith(".scstFounder")
    ):
        return (
            str(new_value).lower() == "true"
            or new_value is True
            or new_value == "Yes"
            or str(new_value).lower() == "yes"
        )
    if kind == "float" or field_key in (
        "valuation",
        "fundingProvided",
        "revenueFY25_26",
        "revenueFY24_25",
        "revenueFY23_24",
        "revenueFY22_23",
        "revenueFY21_22",
    ) or field_key.endswith(".amount"):
        return float(new_value or 0) or 0.0
    if kind == "int" or field_key in ("companyEstablishedYear", "jobsFullTime", "jobsPartTime"):
        return int(float(new_value or 0)) or 0
    if (
        kind == "date"
        or field_key in ("incorporationDate", "ipFilingDate", "incubationJoinDate")
        or field_key.endswith(".date")
    ):
        d = safe_date(new_value, datetime.utcnow())
        return d or datetime.utcnow()
    if field_key == "locations":
        if isinstance(new_value, str):
            return [x.strip() for x in new_value.split(",") if x.strip()]
        return list(new_value or [])
    if kind == "enum" or field_key == "status":
        return StartupStatus(str(new_value))
    return new_value


def apply_admin_field_edit(
    db: Session,
    startup: Startup,
    *,
    field_key: str,
    field_label: str,
    new_value: Any,
    admin_id: str,
) -> None:
    old_val_disp = None

    if "." in field_key:
        parts = field_key.split(".")
        relation = parts[0]
        index = int(parts[1])
        child_field = parts[2]
        if relation == "founders":
            arr = sorted(startup.founders or [], key=lambda x: x.id)
            if index < 0 or index >= len(arr):
                raise HTTPException(
                    status_code=400,
                    detail={"error": f"Could not find founders at index {index}"},
                )
            child = arr[index]
            attr = FOUNDER_CHILD.get(child_field)
            if not attr:
                raise HTTPException(status_code=400, detail={"error": "Unknown founder field"})
            old_val_disp = getattr(child, attr)
            fk = f"{relation}.{index}.{child_field}"
            parsed = _parse_value(fk, new_value, "", old_val_disp)
            setattr(child, attr, parsed)
        elif relation == "fundsRaised":
            arr = sorted(startup.funds_raised or [], key=lambda x: x.id)
            if index < 0 or index >= len(arr):
                raise HTTPException(
                    status_code=400,
                    detail={"error": f"Could not find fundsRaised at index {index}"},
                )
            child = arr[index]
            attr = FUNDING_CHILD.get(child_field)
            if not attr:
                raise HTTPException(status_code=400, detail={"error": "Unknown funding field"})
            old_val_disp = getattr(child, attr)
            if attr == "date":
                parsed = safe_date(new_value, datetime.utcnow())
                setattr(child, attr, parsed)
            elif attr == "amount":
                setattr(child, attr, float(new_value or 0))
            else:
                setattr(child, attr, new_value)
        else:
            raise HTTPException(status_code=400, detail={"error": "Unknown relation"})
    else:
        spec = TOP_LEVEL.get(field_key)
        if not spec:
            raise HTTPException(status_code=400, detail={"error": f"Unsupported fieldKey {field_key}"})
        attr_name, kind = spec
        old_val_disp = getattr(startup, attr_name)
        parsed = _parse_value(field_key, new_value, kind, old_val_disp)
        setattr(startup, attr_name, parsed)

    safe_old = old_val_disp if old_val_disp is not None else "Empty"
    safe_new = str(new_value)

    db.add(startup)
    db.flush()

    eh = EditHistory(
        id=new_cuid(),
        startup_id=startup.id,
        field_key=field_key,
        field_label=field_label,
        old_value=str(safe_old),
        new_value=safe_new,
        edited_by_id=admin_id,
        created_at=datetime.utcnow(),
    )
    db.add(eh)

    n = Notification(
        id=new_cuid(),
        startup_id=startup.id,
        notification_type="edit",
        field_key=field_key,
        field_label=field_label,
        old_value=str(safe_old),
        new_value=safe_new,
        message=f'Admin updated {field_label} to "{safe_new}"',
        created_by_id=admin_id,
        read=False,
        created_at=datetime.utcnow(),
    )
    db.add(n)

    if owner and owner.email:
        email_data = {
            "actionType": "edit",
            "userName": owner.name,
            "startupName": startup.name,
            "fieldLabel": field_label,
            "oldValue": str(safe_old),
            "newValue": safe_new,
            "portalUrl": f"{settings.frontend_url}/startup/{startup.id}?highlight={field_key}",
        }
        if background_tasks:
            background_tasks.add_task(send_email_with_template, owner.email, "admin_activity", email_data)
        else:
            try:
                send_email_with_template(owner.email, "admin_activity", email_data)
            except Exception:
                pass

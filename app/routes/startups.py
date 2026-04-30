"""Startup CRUD + admin — parity with backend startupRoutes.js + startupController.js."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session, joinedload, selectinload

from app.asset_resolve import serialize_startup_for_client_async
from app.config import settings
from app.database import get_db
from app.deps import TokenUser, check_admin, protect
from app.mail_out import send_email_with_template
from app.models import (
    AdminComment,
    AdminNotification,
    EditHistory,
    Founder,
    Funding,
    Notification,
    Startup,
    StartupStatus,
    User,
)
from app.s3_canonical import strip_aws_presigned_query
from app.startups.documents import normalize_documents
from app.startups.mapping import founder_to_camel, funding_to_camel, startup_scalars_camel
from app.startups.edit_handlers import apply_admin_field_edit
from app.startups.utils import normalize_trl, safe_date, to_bool, to_num, to_num_or_null
from app.util_ids import new_cuid

router = APIRouter(prefix="/api/startups", tags=["startups"])


async def _finalize_startup(db: Session, row: Startup, opts: dict | None = None) -> dict:
    base = startup_scalars_camel(row)
    base["founders"] = [founder_to_camel(f) for f in (row.founders or [])]
    base["fundsRaised"] = [funding_to_camel(fr) for fr in (row.funds_raised or [])]
    out = await serialize_startup_for_client_async(base, opts or {})
    out["_id"] = row.id
    return out


def _comment_json(c: AdminComment, creator_name: str | None = None, creator_email: str | None = None) -> dict:
    d = {
        "id": c.id,
        "startupId": c.startup_id,
        "text": c.text,
        "fieldKey": c.field_key,
        "createdById": c.created_by_id,
        "createdAt": c.created_at.isoformat() + "Z" if c.created_at and c.created_at.tzinfo is None else (c.created_at.isoformat() if c.created_at else None),
        "createdBy": {"name": creator_name, "email": creator_email},
    }
    return {**d, "_id": c.id}


def _edit_json(e: EditHistory, editor_name=None, editor_email=None) -> dict:
    d = {
        "id": e.id,
        "startupId": e.startup_id,
        "fieldKey": e.field_key,
        "fieldLabel": e.field_label,
        "oldValue": e.old_value,
        "newValue": e.new_value,
        "editedById": e.edited_by_id,
        "createdAt": e.created_at.isoformat() + "Z" if e.created_at and e.created_at.tzinfo is None else (e.created_at.isoformat() if e.created_at else None),
        "editedBy": {"name": editor_name, "email": editor_email},
    }
    return {**d, "_id": e.id}


def _notify_json(n: Notification, creator_name=None) -> dict:
    d = {
        "id": n.id,
        "startupId": n.startup_id,
        "type": n.notification_type,
        "fieldKey": n.field_key,
        "fieldLabel": n.field_label,
        "oldValue": n.old_value,
        "newValue": n.new_value,
        "message": n.message,
        "createdById": n.created_by_id,
        "read": n.read,
        "createdAt": n.created_at.isoformat() + "Z" if n.created_at and n.created_at.tzinfo is None else (n.created_at.isoformat() if n.created_at else None),
        "createdBy": {"name": creator_name},
    }
    return {**d, "_id": n.id}


def _admin_notify_json(n: AdminNotification, changer_name=None, startup_name=None) -> dict:
    d = {
        "id": n.id,
        "startupId": n.startup_id,
        "type": n.notification_type,
        "fieldKey": n.field_key,
        "fieldLabel": n.field_label,
        "oldValue": n.old_value,
        "newValue": n.new_value,
        "message": n.message,
        "changedById": n.changed_by_id,
        "read": n.read,
        "createdAt": n.created_at.isoformat() + "Z" if n.created_at and n.created_at.tzinfo is None else (n.created_at.isoformat() if n.created_at else None),
        "changedBy": {"name": changer_name},
        "startup": {"name": startup_name} if startup_name else None,
    }
    return {**d, "_id": n.id}


# ---- Public / user ----


@router.get("")
async def get_approved_startups(
    db: Session = Depends(get_db),
    page: int = Query(1),
    limit: int = Query(10),
):
    skip = (page - 1) * limit
    rows = (
        db.execute(
            select(Startup)
            .where(or_(Startup.is_approved.is_(True), Startup.status == StartupStatus.approved))
            .options(selectinload(Startup.founders), selectinload(Startup.funds_raised))
            .order_by(Startup.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    out = []
    for s in rows:
        out.append(await _finalize_startup(db, s, {"lightList": True}))
    return out


@router.post("")
async def create_startup(body: dict, user: TokenUser = Depends(protect), db: Session = Depends(get_db)):
    uid = user.id
    existing = db.execute(select(Startup).where(Startup.created_by_id == uid)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "You can submit only one startup.",
                "startupId": existing.id,
                "status": existing.status.value,
            },
        )
    b = body
    now = datetime.utcnow()
    sid = new_cuid()

    logo_val = b.get("logo")
    if isinstance(logo_val, str):
        logo_val = strip_aws_presigned_query(logo_val.strip())
    elif isinstance(logo_val, dict) and logo_val.get("name"):
        logo_val = logo_val.get("name")
    else:
        logo_val = logo_val or ""

    s = Startup(
        id=sid,
        created_by_id=uid,
        name=b.get("name") or "Untitled Startup",
        logo=logo_val,
        documents=normalize_documents(b.get("documents")),
        website=b.get("website") or "",
        industry=b.get("industry") or "",
        startup_description=b.get("startupDescription") or "",
        product_description=b.get("productDescription") or "",
        stage=b.get("stage") or "",
        trl=normalize_trl(b.get("trl")),
        incorporation_date=safe_date(b.get("incorporationDate"), now),
        roc=b.get("roc"),
        cin=b.get("cin"),
        company_established_year=to_num(b.get("companyEstablishedYear")) if b.get("companyEstablishedYear") is not None else None,
        locations=list(b.get("locations") or []),
        core_technology=b.get("coreTechnology") or "",
        ip_status=(b.get("ipStatus") or {}).get("status") if isinstance(b.get("ipStatus"), dict) else b.get("ipStatus"),
        ip_title=(b.get("ipStatus") or {}).get("title") if isinstance(b.get("ipStatus"), dict) else None,
        ip_filing_date=safe_date((b.get("ipStatus") or {}).get("filingDate")) if isinstance(b.get("ipStatus"), dict) else None,
        ip_current_status=(b.get("ipStatus") or {}).get("currentStatus") if isinstance(b.get("ipStatus"), dict) else None,
        roadmap=b.get("roadmap") or "",
        revenue_fy25_26=to_num_or_null((b.get("revenue") or {}).get("fy2025_26")) if b.get("revenue") else None,
        revenue_fy24_25=to_num_or_null((b.get("revenue") or {}).get("fy2024_25")) if b.get("revenue") else None,
        revenue_fy23_24=to_num_or_null((b.get("revenue") or {}).get("fy2023_24")) if b.get("revenue") else None,
        revenue_fy22_23=to_num_or_null((b.get("revenue") or {}).get("fy2022_23")) if b.get("revenue") else None,
        revenue_fy21_22=to_num_or_null((b.get("revenue") or {}).get("fy2021_22")) if b.get("revenue") else None,
        valuation=to_num(b.get("valuation")),
        captable=b.get("captable"),
        jobs_full_time=to_num((b.get("jobs") or {}).get("fullTime")),
        jobs_part_time=to_num((b.get("jobs") or {}).get("partTime")),
        achievements=b.get("achievements") or "",
        incubation_join_date=safe_date(
            (b.get("incubation") or {}).get("joinDate"), now
        ),
        support_provided=(b.get("incubation") or {}).get("support", {}).get("supportProvided") or "",
        support_funding=to_bool((b.get("incubation") or {}).get("support", {}).get("funding")),
        support_office_space=to_bool((b.get("incubation") or {}).get("support", {}).get("officeSpace")),
        support_industry_connects=to_bool((b.get("incubation") or {}).get("support", {}).get("industryConnects")),
        support_investor_connects=to_bool((b.get("incubation") or {}).get("support", {}).get("investorConnects")),
        funding_provided=to_num((b.get("incubation") or {}).get("support", {}).get("fundingProvided")),
        milestones_committed=b.get("incubation", {}).get("milestonesCommitted") or "",
        milestones_achieved=b.get("incubation", {}).get("milestonesAchieved") or "",
        status=StartupStatus.submitted,
        is_approved=False,
        rejection_reason="",
        dismissed_activity_keys=[],
        created_at=now,
        updated_at=now,
    )
    db.add(s)
    db.flush()

    for f in b.get("founders") or []:
        if not (f.get("fullName") or f.get("email")):
            continue
        db.add(
            Founder(
                id=new_cuid(),
                startup_id=sid,
                full_name=f.get("fullName") or "",
                email=f.get("email") or "",
                phone1=f.get("phone1") or "",
                phone2=f.get("phone2") or "",
                linkedin=f.get("linkedin") or "",
                education=f.get("education") or "",
                woman_founder="No" if f.get("womanFounder") == "No" else "Yes",
                scst_founder=to_bool(f.get("scstFounder")),
            )
        )

    for fr in b.get("fundsRaised") or []:
        if not (fr.get("source") or fr.get("amount")):
            continue
        db.add(
            Funding(
                id=new_cuid(),
                startup_id=sid,
                source=fr.get("source") or "",
                fund_type=fr.get("type") or "",
                amount=to_num(fr.get("amount")),
                date=safe_date(fr.get("date"), now),
            )
        )

    db.commit()
    db.refresh(s)
    s = db.execute(
        select(Startup)
        .where(Startup.id == sid)
        .options(selectinload(Startup.founders), selectinload(Startup.funds_raised))
    ).scalar_one()
    return await _finalize_startup(db, s)


@router.get("/my")
async def get_my_startup(user: TokenUser = Depends(protect), db: Session = Depends(get_db)):
    row = (
        db.execute(
            select(Startup)
            .where(Startup.created_by_id == user.id)
            .options(
                selectinload(Startup.founders),
                selectinload(Startup.funds_raised),
                selectinload(Startup.admin_comments),
                selectinload(Startup.edit_history),
                selectinload(Startup.notifications),
            )
            .order_by(Startup.created_at.desc())
        )
        .scalars()
        .first()
    )
    if not row:
        return None

    base = await _finalize_startup(db, row, {"lightList": True})
    # attach comments with creator — simplified load
    comments = []
    for c in row.admin_comments or []:
        creator = db.execute(select(User).where(User.id == c.created_by_id)).scalar_one_or_none()
        comments.append(
            _comment_json(c, creator_name=creator.name if creator else None, creator_email=creator.email if creator else None)
        )
    base["adminComments"] = comments

    edits = []
    for e in row.edit_history or []:
        ed = db.execute(select(User).where(User.id == e.edited_by_id)).scalar_one_or_none()
        edits.append(_edit_json(e, editor_name=ed.name if ed else None, editor_email=ed.email if ed else None))
    base["editHistory"] = edits

    notifs = []
    for n in row.notifications or []:
        cr = db.execute(select(User).where(User.id == n.created_by_id)).scalar_one_or_none()
        notifs.append(_notify_json(n, creator_name=cr.name if cr else None))
    base["notifications"] = notifs
    return base


@router.put("/{startup_id}")
async def update_startup(
    startup_id: str,
    body: dict,
    user: TokenUser = Depends(protect),
    db: Session = Depends(get_db),
):
    uid = user.id
    current = db.execute(
        select(Startup)
        .where(Startup.id == startup_id)
        .options(selectinload(Startup.admin_comments))
    ).scalar_one_or_none()
    if not current or current.created_by_id != uid:
        raise HTTPException(status_code=404, detail={"message": "Startup not found or unauthorized ❌"})
    b = body
    removed_comment_ids: list[str] = []
    admin_notifications_data: list[dict] = []

    flat = startup_scalars_camel(current)
    for comment in current.admin_comments or []:
        key = comment.field_key
        if not key:
            continue
        old_value = flat.get(key)
        new_value = b.get(key)
        if old_value is not None and new_value is not None and str(old_value) != str(new_value):
            removed_comment_ids.append(comment.id)
            admin_notifications_data.append(
                {
                    "type": "user_response",
                    "fieldKey": key,
                    "fieldLabel": key,
                    "oldValue": str(old_value) if old_value is not None else None,
                    "newValue": str(new_value) if new_value is not None else None,
                    "message": f"User corrected '{key}' after admin feedback",
                    "changedById": uid,
                    "read": False,
                }
            )

    if removed_comment_ids:
        db.execute(delete(AdminComment).where(AdminComment.id.in_(removed_comment_ids)))

    if b.get("founders") is not None:
        db.execute(delete(Founder).where(Founder.startup_id == current.id))
    if b.get("fundsRaised") is not None:
        db.execute(delete(Funding).where(Funding.startup_id == current.id))

    logo_u = b.get("logo")
    if isinstance(logo_u, str):
        logo_u = strip_aws_presigned_query(logo_u.strip())
    elif logo_u is not None and not isinstance(logo_u, str):
        logo_u = b.get("logo")

    if isinstance(logo_u, dict) and logo_u.get("name"):
        logo_u = logo_u.get("name")

    now = datetime.utcnow()
    current.name = b.get("name")
    current.logo = logo_u
    current.website = b.get("website")
    current.industry = b.get("industry")
    current.startup_description = b.get("startupDescription")
    current.product_description = b.get("productDescription")
    current.stage = b.get("stage")
    current.trl = normalize_trl(b.get("trl"))
    current.incorporation_date = safe_date(b.get("incorporationDate"))
    current.roc = b.get("roc")
    current.cin = b.get("cin")
    current.company_established_year = to_num(b.get("companyEstablishedYear")) if b.get("companyEstablishedYear") is not None else None
    current.locations = list(b.get("locations") or [])
    current.core_technology = b.get("coreTechnology")
    current.ip_status = (b.get("ipStatus") or {}).get("status") if isinstance(b.get("ipStatus"), dict) else b.get("ipStatus")
    current.ip_title = (b.get("ipStatus") or {}).get("title") if isinstance(b.get("ipStatus"), dict) else None
    current.ip_filing_date = safe_date((b.get("ipStatus") or {}).get("filingDate")) if isinstance(b.get("ipStatus"), dict) else None
    current.ip_current_status = (b.get("ipStatus") or {}).get("currentStatus") if isinstance(b.get("ipStatus"), dict) else None
    current.roadmap = b.get("roadmap") or ""
    current.revenue_fy25_26 = to_num_or_null((b.get("revenue") or {}).get("fy2025_26")) if b.get("revenue") else current.revenue_fy25_26
    current.revenue_fy24_25 = to_num_or_null((b.get("revenue") or {}).get("fy2024_25")) if b.get("revenue") else current.revenue_fy24_25
    current.revenue_fy23_24 = to_num_or_null((b.get("revenue") or {}).get("fy2023_24")) if b.get("revenue") else current.revenue_fy23_24
    current.revenue_fy22_23 = to_num_or_null((b.get("revenue") or {}).get("fy2022_23")) if b.get("revenue") else current.revenue_fy22_23
    current.revenue_fy21_22 = to_num_or_null((b.get("revenue") or {}).get("fy2021_22")) if b.get("revenue") else current.revenue_fy21_22
    current.valuation = to_num(b.get("valuation"))
    current.captable = b.get("captable")
    current.jobs_full_time = to_num((b.get("jobs") or {}).get("fullTime")) if b.get("jobs") else current.jobs_full_time
    current.jobs_part_time = to_num((b.get("jobs") or {}).get("partTime")) if b.get("jobs") else current.jobs_part_time
    current.achievements = b.get("achievements") or ""
    ij = b.get("incubationJoinDate") or (b.get("incubation") or {}).get("joinDate")
    current.incubation_join_date = safe_date(ij) if ij else current.incubation_join_date
    current.support_provided = b.get("supportProvided") or (b.get("incubation") or {}).get("support", {}).get("supportProvided") or ""
    current.support_funding = (
        to_bool(b.get("supportFunding"))
        if b.get("supportFunding") is not None
        else to_bool((b.get("incubation") or {}).get("support", {}).get("funding"))
    )
    current.support_office_space = (
        to_bool(b.get("supportOfficeSpace"))
        if b.get("supportOfficeSpace") is not None
        else to_bool((b.get("incubation") or {}).get("support", {}).get("officeSpace"))
    )
    current.support_industry_connects = (
        to_bool(b.get("supportIndustryConnects"))
        if b.get("supportIndustryConnects") is not None
        else to_bool((b.get("incubation") or {}).get("support", {}).get("industryConnects"))
    )
    current.support_investor_connects = (
        to_bool(b.get("supportInvestorConnects"))
        if b.get("supportInvestorConnects") is not None
        else to_bool((b.get("incubation") or {}).get("support", {}).get("investorConnects"))
    )
    current.funding_provided = (
        to_num(b.get("fundingProvided"))
        if b.get("fundingProvided") is not None
        else to_num((b.get("incubation") or {}).get("support", {}).get("fundingProvided"))
    )
    current.milestones_committed = b.get("milestonesCommitted") or (b.get("incubation") or {}).get("milestonesCommitted") or ""
    current.milestones_achieved = b.get("milestonesAchieved") or (b.get("incubation") or {}).get("milestonesAchieved") or ""
    current.status = StartupStatus.under_review
    current.is_approved = False
    current.rejection_reason = ""
    current.updated_at = now

    if isinstance(b.get("documents"), list):
        current.documents = normalize_documents(b.get("documents"))

    for f in b.get("founders") or []:
        if not (f.get("fullName") or f.get("email")):
            continue
        db.add(
            Founder(
                id=new_cuid(),
                startup_id=current.id,
                full_name=f.get("fullName") or "",
                email=f.get("email") or "",
                phone1=f.get("phone1") or "",
                phone2=f.get("phone2") or "",
                linkedin=f.get("linkedin") or "",
                education=f.get("education") or "",
                woman_founder=f.get("womanFounder") if f.get("womanFounder") == "No" else "Yes",
                scst_founder=to_bool(f.get("scstFounder")),
            )
        )

    for fr in b.get("fundsRaised") or []:
        if not (fr.get("source") or fr.get("amount")):
            continue
        db.add(
            Funding(
                id=new_cuid(),
                startup_id=current.id,
                source=fr.get("source") or "",
                fund_type=fr.get("type") or "",
                amount=to_num(fr.get("amount")),
                date=safe_date(fr.get("date"), now),
            )
        )

    for ad in admin_notifications_data:
        db.add(
            AdminNotification(
                id=new_cuid(),
                startup_id=current.id,
                notification_type=ad["type"],
                field_key=ad["fieldKey"],
                field_label=ad["fieldLabel"],
                old_value=ad["oldValue"],
                new_value=ad["newValue"],
                message=ad["message"],
                changed_by_id=ad["changedById"],
                read=ad["read"],
                created_at=now,
            )
        )

    db.add(current)
    db.commit()

    row = db.execute(
        select(Startup)
        .where(Startup.id == current.id)
        .options(selectinload(Startup.founders), selectinload(Startup.funds_raised))
    ).scalar_one()
    return await _finalize_startup(db, row)


# Literals before /{startup_id}


@router.get("/pending")
async def get_pending_startups(admin: TokenUser = Depends(check_admin), db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(Startup)
            .where(
                Startup.status.in_([StartupStatus.submitted, StartupStatus.under_review]),
                Startup.is_approved.is_(False),
            )
            .options(selectinload(Startup.founders), selectinload(Startup.funds_raised), joinedload(Startup.created_by))
        )
        .scalars()
        .unique()
        .all()
    )
    out = []
    for s in rows:
        d = await _finalize_startup(db, s, {"lightList": True})
        cb = s.created_by
        d["createdBy"] = {"name": cb.name if cb else None, "email": cb.email if cb else None}
        out.append(d)
    return out


@router.get("/admin")
async def get_admin_startups(
    admin: TokenUser = Depends(check_admin),
    db: Session = Depends(get_db),
    status: str = Query("all"),
):
    q = select(Startup).options(
        selectinload(Startup.founders), selectinload(Startup.funds_raised), joinedload(Startup.created_by)
    )
    if status == "pending":
        q = q.where(
            Startup.status.in_([StartupStatus.submitted, StartupStatus.under_review]),
            Startup.is_approved.is_(False),
        )
    elif status == "approved":
        q = q.where(or_(Startup.is_approved.is_(True), Startup.status == StartupStatus.approved))
    elif status == "rejected":
        q = q.where(Startup.status == StartupStatus.rejected)

    rows = (
        db.execute(q.order_by(Startup.created_at.desc())).scalars().unique().all()
    )
    out = []
    for s in rows:
        d = await _finalize_startup(db, s, {"lightList": True})
        cb = s.created_by
        d["createdBy"] = {"name": cb.name if cb else None, "email": cb.email if cb else None}
        out.append(d)
    return out


@router.get("/admin/notifications")
async def get_global_admin_notifications(admin: TokenUser = Depends(check_admin), db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(AdminNotification)
            .options(joinedload(AdminNotification.changed_by), joinedload(AdminNotification.startup))
            .order_by(AdminNotification.created_at.desc())
            .limit(50)
        )
        .scalars()
        .unique()
        .all()
    )
    out = []
    for n in rows:
        sn = n.startup.name if n.startup else None
        cn = n.changed_by.name if n.changed_by else None
        out.append(_admin_notify_json(n, changer_name=cn, startup_name=sn))
    return out


@router.get("/{startup_id}/comments")
async def get_admin_comments(startup_id: str, db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(AdminComment)
            .where(AdminComment.startup_id == startup_id)
            .options(joinedload(AdminComment.created_by))
            .order_by(AdminComment.created_at.desc())
        )
        .scalars()
        .unique()
        .all()
    )
    # AdminComment model needs relationship created_by — add to model if missing
    out = []
    for c in rows:
        cr = getattr(c, "created_by", None)
        out.append(
            _comment_json(
                c,
                creator_name=cr.name if cr else None,
                creator_email=cr.email if cr else None,
            )
        )
    return out


@router.post("/{startup_id}/comments")
async def add_admin_comment(
    startup_id: str,
    body: dict,
    admin: TokenUser = Depends(check_admin),
    db: Session = Depends(get_db),
):
    text = body.get("text")
    field_key = body.get("fieldKey")
    admin_id = admin.id
    startup = db.get(Startup, startup_id)
    if not startup:
        raise HTTPException(status_code=404, detail={"error": "Startup not found"})

    c1 = AdminComment(
        id=new_cuid(),
        startup_id=startup_id,
        text=text,
        field_key=field_key,
        created_by_id=admin_id,
        created_at=datetime.utcnow(),
    )
    db.add(c1)

    preview = (text or "")[:60] + ("..." if len(text or "") > 60 else "")
    for _ in range(2):
        db.add(
            Notification(
                id=new_cuid(),
                startup_id=startup_id,
                notification_type="comment",
                field_key=field_key,
                field_label=field_key or "General",
                message=f"Admin added a comment: {preview}",
                created_by_id=admin_id,
                read=False,
                created_at=datetime.utcnow(),
            )
        )

    owner = db.get(User, startup.created_by_id)
    if owner and owner.email:
        try:
            send_email_with_template(
                owner.email,
                "admin_activity",
                {
                    "actionType": "comment",
                    "userName": owner.name,
                    "startupName": startup.name,
                    "fieldLabel": field_key or "General",
                    "commentText": text,
                    "portalUrl": f"{settings.frontend_url}/startup/{startup.id}?highlight={field_key or ''}",
                },
            )
        except Exception:
            pass

    db.commit()
    return {"success": True, "message": "Comment added"}


@router.get("/{startup_id}/edits")
async def get_edit_history(startup_id: str, db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(EditHistory)
            .where(EditHistory.startup_id == startup_id)
            .options(joinedload(EditHistory.edited_by))
            .order_by(EditHistory.created_at.desc())
        )
        .scalars()
        .unique()
        .all()
    )
    out = []
    for e in rows:
        ed = e.edited_by
        out.append(_edit_json(e, editor_name=ed.name if ed else None, editor_email=ed.email if ed else None))
    return out


@router.post("/{startup_id}/edits")
async def add_edit_history(
    startup_id: str,
    body: dict,
    admin: TokenUser = Depends(check_admin),
    db: Session = Depends(get_db),
):
    startup = db.execute(
        select(Startup)
        .where(Startup.id == startup_id)
        .options(selectinload(Startup.founders), selectinload(Startup.funds_raised))
    ).scalar_one_or_none()
    if not startup:
        raise HTTPException(status_code=404, detail={"error": "Startup not found"})

    field_key = body.get("fieldKey")
    field_label = body.get("fieldLabel")
    new_value = body.get("newValue")
    try:
        apply_admin_field_edit(
            db,
            startup,
            field_key=field_key,
            field_label=field_label or field_key,
            new_value=new_value,
            admin_id=admin.id,
        )
        db.commit()
        return {"success": True, "message": "Field updated"}
    except HTTPException:
        db.rollback()
        raise


@router.get("/{startup_id}/field-history")
async def get_field_history(
    startup_id: str,
    db: Session = Depends(get_db),
    fieldKey: str = Query(..., alias="fieldKey"),
):
    edits = (
        db.execute(
            select(EditHistory)
            .where(EditHistory.startup_id == startup_id, EditHistory.field_key == fieldKey)
            .options(joinedload(EditHistory.edited_by))
            .order_by(EditHistory.created_at.desc())
        )
        .scalars()
        .unique()
        .all()
    )
    comments = (
        db.execute(
            select(AdminComment)
            .where(AdminComment.startup_id == startup_id, AdminComment.field_key == fieldKey)
            .options(joinedload(AdminComment.created_by))
            .order_by(AdminComment.created_at.desc())
        )
        .scalars()
        .unique()
        .all()
    )
    ei = []
    for e in edits:
        ed = e.edited_by
        ei.append(_edit_json(e, editor_name=ed.name if ed else None, editor_email=ed.email if ed else None))
    ci = []
    for c in comments:
        cr = c.created_by
        ci.append(_comment_json(c, creator_name=cr.name if cr else None, creator_email=cr.email if cr else None))
    return {"fieldKey": fieldKey, "edits": ei, "comments": ci}


@router.get("/{startup_id}/notifications")
async def get_notifications(startup_id: str, user: TokenUser = Depends(protect), db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(Notification)
            .where(Notification.startup_id == startup_id)
            .options(joinedload(Notification.created_by))
            .order_by(Notification.created_at.desc())
        )
        .scalars()
        .unique()
        .all()
    )
    out = []
    for n in rows:
        cr = n.created_by
        out.append(_notify_json(n, creator_name=cr.name if cr else None))
    return out


@router.get("/{startup_id}/admin-notifications")
async def get_startup_admin_notifications(
    startup_id: str, admin: TokenUser = Depends(check_admin), db: Session = Depends(get_db)
):
    rows = (
        db.execute(
            select(AdminNotification)
            .where(AdminNotification.startup_id == startup_id)
            .options(joinedload(AdminNotification.changed_by))
            .order_by(AdminNotification.created_at.desc())
        )
        .scalars()
        .unique()
        .all()
    )
    out = []
    for n in rows:
        ch = n.changed_by
        out.append(_admin_notify_json(n, changer_name=ch.name if ch else None))
    return out


@router.post("/{startup_id}/notifications/read-all")
async def read_all_notifications(startup_id: str, user: TokenUser = Depends(protect), db: Session = Depends(get_db)):
    db.execute(
        update(Notification)
        .where(Notification.startup_id == startup_id, Notification.read.is_(False))
        .values(read=True)
    )
    db.execute(
        update(AdminNotification)
        .where(AdminNotification.startup_id == startup_id, AdminNotification.read.is_(False))
        .values(read=True)
    )
    db.commit()
    return {"success": True, "message": "All notifications marked as read"}


@router.put("/{startup_id}/notifications/{notification_id}")
async def mark_notification_read(
    startup_id: str,
    notification_id: str,
    user: TokenUser = Depends(protect),
    db: Session = Depends(get_db),
):
    n = db.get(Notification, notification_id)
    if n:
        n.read = True
        db.add(n)
        db.commit()
    rows = (
        db.execute(
            select(Notification)
            .where(Notification.startup_id == startup_id)
            .options(joinedload(Notification.created_by))
        )
        .scalars()
        .unique()
        .all()
    )
    out = []
    for x in rows:
        cr = x.created_by
        out.append(_notify_json(x, creator_name=cr.name if cr else None))
    return out


@router.put("/{startup_id}/dismissed-activity")
async def add_dismissed_activity_key(
    startup_id: str,
    body: dict,
    user: TokenUser = Depends(protect),
    db: Session = Depends(get_db),
):
    key = body.get("key")
    startup = db.get(Startup, startup_id)
    if not startup:
        raise HTTPException(status_code=404, detail={"error": "Not found"})
    dismissed = list(startup.dismissed_activity_keys or [])
    if key not in dismissed:
        dismissed = dismissed + [key]
        startup.dismissed_activity_keys = dismissed
        db.add(startup)
        db.commit()
    return dismissed


@router.put("/{startup_id}/approve")
async def approve_startup(startup_id: str, admin: TokenUser = Depends(check_admin), db: Session = Depends(get_db)):
    s = db.get(Startup, startup_id)
    if not s:
        raise HTTPException(status_code=404, detail={"message": "Startup not found"})
    s.is_approved = True
    s.status = StartupStatus.approved
    s.rejection_reason = ""
    db.add(s)
    db.commit()
    db.refresh(s)
    return await _finalize_startup(db, s)


@router.put("/{startup_id}/reject")
async def reject_startup(startup_id: str, body: dict, admin: TokenUser = Depends(check_admin), db: Session = Depends(get_db)):
    s = db.get(Startup, startup_id)
    if not s:
        raise HTTPException(status_code=404, detail={"message": "Startup not found"})
    s.is_approved = False
    s.status = StartupStatus.rejected
    s.rejection_reason = body.get("rejectionReason") or "Reason not provided"
    db.add(s)
    db.commit()
    db.refresh(s)
    return await _finalize_startup(db, s)


@router.delete("/{startup_id}")
async def delete_startup(startup_id: str, admin: TokenUser = Depends(check_admin), db: Session = Depends(get_db)):
    s = db.get(Startup, startup_id)
    if not s:
        raise HTTPException(status_code=404, detail={"error": "Not found"})
    db.delete(s)
    db.commit()
    return {"message": "Deleted successfully ✅"}


@router.get("/{startup_id}")
async def get_startup_by_id(startup_id: str, db: Session = Depends(get_db)):
    row = db.execute(
        select(Startup)
        .where(Startup.id == startup_id)
        .options(
            selectinload(Startup.founders),
            selectinload(Startup.funds_raised),
            selectinload(Startup.admin_comments),
            selectinload(Startup.edit_history),
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail={"message": "Startup not found"})
    base = await _finalize_startup(db, row)
    ac = []
    for c in row.admin_comments or []:
        cu = db.get(User, c.created_by_id)
        ac.append(_comment_json(c, creator_name=cu.name if cu else None, creator_email=cu.email if cu else None))
    base["adminComments"] = ac
    eh = []
    for e in row.edit_history or []:
        ed = db.get(User, e.edited_by_id)
        eh.append(_edit_json(e, editor_name=ed.name if ed else None, editor_email=ed.email if ed else None))
    base["editHistory"] = eh
    return base

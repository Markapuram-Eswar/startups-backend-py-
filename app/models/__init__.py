from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Role(str, enum.Enum):
    user = "user"
    admin = "admin"


class StartupStatus(str, enum.Enum):
    submitted = "submitted"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"


role_enum = ENUM(Role, name="Role", create_type=False)
startup_status_enum = ENUM(StartupStatus, name="StartupStatus", create_type=False)


class User(Base):
    __tablename__ = "User"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    login_otp_hash: Mapped[Optional[str]] = mapped_column("loginOtpHash", Text, nullable=True)
    login_otp_expires_at: Mapped[Optional[datetime]] = mapped_column(
        "loginOtpExpiresAt", DateTime(timezone=False), nullable=True
    )
    reset_otp_hash: Mapped[Optional[str]] = mapped_column("resetOtpHash", Text, nullable=True)
    reset_otp_expires_at: Mapped[Optional[datetime]] = mapped_column(
        "resetOtpExpiresAt", DateTime(timezone=False), nullable=True
    )
    role: Mapped[Role] = mapped_column(role_enum, nullable=False)
    created_by_admin_id: Mapped[Optional[str]] = mapped_column("createdByAdminId", Text, nullable=True)
    created_by_admin_name: Mapped[Optional[str]] = mapped_column("createdByAdminName", Text, nullable=True)
    welcome_email_sent: Mapped[bool] = mapped_column(
        "welcomeEmailSent", Boolean, nullable=False, server_default=text("false")
    )
    force_password_reset: Mapped[bool] = mapped_column(
        "forcePasswordReset", Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", DateTime(timezone=False), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    startups_created: Mapped[list["Startup"]] = relationship(
        back_populates="created_by",
        foreign_keys="Startup.created_by_id",
    )


class Startup(Base):
    __tablename__ = "Startup"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    is_approved: Mapped[bool] = mapped_column(
        "isApproved", Boolean, nullable=False, server_default=text("false")
    )
    status: Mapped[StartupStatus] = mapped_column(startup_status_enum, nullable=False)
    rejection_reason: Mapped[str] = mapped_column(
        "rejectionReason", Text, nullable=False, server_default=text("''")
    )
    created_by_id: Mapped[str] = mapped_column("createdById", String, ForeignKey("User.id"))

    name: Mapped[str] = mapped_column(Text, nullable=False)
    logo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    documents: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    website: Mapped[str] = mapped_column(Text, nullable=False)
    industry: Mapped[str] = mapped_column(Text, nullable=False)
    startup_description: Mapped[str] = mapped_column("startupDescription", Text, nullable=False)
    product_description: Mapped[str] = mapped_column("productDescription", Text, nullable=False)
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    trl: Mapped[str] = mapped_column(Text, nullable=False)
    incorporation_date: Mapped[datetime] = mapped_column(
        "incorporationDate", DateTime(timezone=False), nullable=False
    )
    roc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cin: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    company_established_year: Mapped[Optional[int]] = mapped_column(
        "companyEstablishedYear", Integer, nullable=True
    )
    locations: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )

    core_technology: Mapped[str] = mapped_column("coreTechnology", Text, nullable=False)
    ip_status: Mapped[Optional[str]] = mapped_column("ipStatus", Text, nullable=True)
    ip_title: Mapped[Optional[str]] = mapped_column("ipTitle", Text, nullable=True)
    ip_filing_date: Mapped[Optional[datetime]] = mapped_column(
        "ipFilingDate", DateTime(timezone=False), nullable=True
    )
    ip_current_status: Mapped[Optional[str]] = mapped_column("ipCurrentStatus", Text, nullable=True)
    roadmap: Mapped[str] = mapped_column(Text, nullable=False)

    revenue_fy25_26: Mapped[Optional[float]] = mapped_column("revenueFY25_26", Float, nullable=True)
    revenue_fy24_25: Mapped[Optional[float]] = mapped_column("revenueFY24_25", Float, nullable=True)
    revenue_fy23_24: Mapped[Optional[float]] = mapped_column("revenueFY23_24", Float, nullable=True)
    revenue_fy22_23: Mapped[Optional[float]] = mapped_column("revenueFY22_23", Float, nullable=True)
    revenue_fy21_22: Mapped[Optional[float]] = mapped_column("revenueFY21_22", Float, nullable=True)

    valuation: Mapped[float] = mapped_column(Float, nullable=False)
    captable: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    jobs_full_time: Mapped[int] = mapped_column("jobsFullTime", Integer, nullable=False)
    jobs_part_time: Mapped[int] = mapped_column("jobsPartTime", Integer, nullable=False)
    achievements: Mapped[str] = mapped_column(Text, nullable=False)

    incubation_join_date: Mapped[datetime] = mapped_column(
        "incubationJoinDate", DateTime(timezone=False), nullable=False
    )
    support_provided: Mapped[str] = mapped_column("supportProvided", Text, nullable=False)
    support_funding: Mapped[bool] = mapped_column(
        "supportFunding", Boolean, nullable=False, server_default=text("false")
    )
    support_office_space: Mapped[bool] = mapped_column(
        "supportOfficeSpace", Boolean, nullable=False, server_default=text("false")
    )
    support_industry_connects: Mapped[bool] = mapped_column(
        "supportIndustryConnects", Boolean, nullable=False, server_default=text("false")
    )
    support_investor_connects: Mapped[bool] = mapped_column(
        "supportInvestorConnects", Boolean, nullable=False, server_default=text("false")
    )
    funding_provided: Mapped[float] = mapped_column(
        "fundingProvided", Float, nullable=False, server_default=text("0")
    )

    milestones_committed: Mapped[str] = mapped_column("milestonesCommitted", Text, nullable=False)
    milestones_achieved: Mapped[str] = mapped_column("milestonesAchieved", Text, nullable=False)

    dismissed_activity_keys: Mapped[list[str]] = mapped_column(
        "dismissedActivityKeys", ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )

    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", DateTime(timezone=False), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_id], back_populates="startups_created")
    founders: Mapped[list["Founder"]] = relationship(back_populates="startup", cascade="all, delete-orphan")
    funds_raised: Mapped[list["Funding"]] = relationship(
        back_populates="startup", cascade="all, delete-orphan"
    )
    admin_comments: Mapped[list["AdminComment"]] = relationship(
        back_populates="startup", cascade="all, delete-orphan"
    )
    edit_history: Mapped[list["EditHistory"]] = relationship(
        back_populates="startup", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="startup", cascade="all, delete-orphan"
    )
    admin_notifications: Mapped[list["AdminNotification"]] = relationship(
        back_populates="startup", cascade="all, delete-orphan"
    )


class Founder(Base):
    __tablename__ = "Founder"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    startup_id: Mapped[str] = mapped_column("startupId", String, ForeignKey("Startup.id", ondelete="CASCADE"))
    full_name: Mapped[str] = mapped_column("fullName", Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    phone1: Mapped[str] = mapped_column(Text, nullable=False)
    phone2: Mapped[str] = mapped_column(Text, nullable=False)
    linkedin: Mapped[str] = mapped_column(Text, nullable=False)
    education: Mapped[str] = mapped_column(Text, nullable=False)
    woman_founder: Mapped[str] = mapped_column("womanFounder", Text, nullable=False)
    scst_founder: Mapped[bool] = mapped_column("scstFounder", Boolean, nullable=False)

    startup: Mapped["Startup"] = relationship(back_populates="founders")


class Funding(Base):
    __tablename__ = "Funding"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    startup_id: Mapped[str] = mapped_column("startupId", String, ForeignKey("Startup.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(Text, nullable=False)
    fund_type: Mapped[str] = mapped_column("type", Text, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    startup: Mapped["Startup"] = relationship(back_populates="funds_raised")


class AdminComment(Base):
    __tablename__ = "AdminComment"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    startup_id: Mapped[str] = mapped_column("startupId", String, ForeignKey("Startup.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    field_key: Mapped[Optional[str]] = mapped_column("fieldKey", Text, nullable=True)
    created_by_id: Mapped[str] = mapped_column("createdById", String, ForeignKey("User.id"))
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    startup: Mapped["Startup"] = relationship(back_populates="admin_comments")
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_id])


class EditHistory(Base):
    __tablename__ = "EditHistory"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    startup_id: Mapped[str] = mapped_column("startupId", String, ForeignKey("Startup.id", ondelete="CASCADE"))
    field_key: Mapped[str] = mapped_column("fieldKey", Text, nullable=False)
    field_label: Mapped[str] = mapped_column("fieldLabel", Text, nullable=False)
    old_value: Mapped[Optional[Any]] = mapped_column("oldValue", JSONB, nullable=True)
    new_value: Mapped[Any] = mapped_column("newValue", JSONB, nullable=False)
    edited_by_id: Mapped[str] = mapped_column("editedById", String, ForeignKey("User.id"))
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    startup: Mapped["Startup"] = relationship(back_populates="edit_history")
    edited_by: Mapped["User"] = relationship(foreign_keys=[edited_by_id])


class Notification(Base):
    __tablename__ = "Notification"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    startup_id: Mapped[str] = mapped_column("startupId", String, ForeignKey("Startup.id", ondelete="CASCADE"))
    notification_type: Mapped[str] = mapped_column("type", Text, nullable=False)
    field_key: Mapped[Optional[str]] = mapped_column("fieldKey", Text, nullable=True)
    field_label: Mapped[Optional[str]] = mapped_column("fieldLabel", Text, nullable=True)
    old_value: Mapped[Optional[Any]] = mapped_column("oldValue", JSONB, nullable=True)
    new_value: Mapped[Optional[Any]] = mapped_column("newValue", JSONB, nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[str] = mapped_column("createdById", String, ForeignKey("User.id"))
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    startup: Mapped["Startup"] = relationship(back_populates="notifications")
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_id])


class AdminNotification(Base):
    __tablename__ = "AdminNotification"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    startup_id: Mapped[str] = mapped_column("startupId", String, ForeignKey("Startup.id", ondelete="CASCADE"))
    notification_type: Mapped[str] = mapped_column("type", Text, nullable=False)
    field_key: Mapped[Optional[str]] = mapped_column("fieldKey", Text, nullable=True)
    field_label: Mapped[Optional[str]] = mapped_column("fieldLabel", Text, nullable=True)
    old_value: Mapped[Optional[Any]] = mapped_column("oldValue", JSONB, nullable=True)
    new_value: Mapped[Optional[Any]] = mapped_column("newValue", JSONB, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by_id: Mapped[str] = mapped_column("changedById", String, ForeignKey("User.id"))
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    startup: Mapped["Startup"] = relationship(back_populates="admin_notifications")
    changed_by: Mapped["User"] = relationship(foreign_keys=[changed_by_id])

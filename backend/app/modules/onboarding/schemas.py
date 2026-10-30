from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

ApplicationKind = Literal["individual", "institute"]
ApplicationStatus = Literal["submitted", "changes_requested", "approved", "rejected"]
Decision = Literal["approve", "request_changes", "reject"]


class ApplicationFields(BaseModel):
    """What the applicant fills in (sent as multipart form fields next to the document)."""

    kind: ApplicationKind
    org_name: str = Field(min_length=2, max_length=120)
    subject_ids: list[UUID] = Field(min_length=1, max_length=6)
    experience: str | None = Field(default=None, max_length=2000)
    payout_bank_name: str = Field(min_length=2, max_length=80)
    payout_branch: str | None = Field(default=None, max_length=80)
    payout_account_name: str = Field(min_length=2, max_length=120)
    # Required when applying; on a resubmission, leaving it out keeps the stored number.
    payout_account_number: str | None = Field(default=None, min_length=4, max_length=34)
    accept_terms: bool

    @field_validator("org_name", "payout_bank_name", "payout_account_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return " ".join(v.split())

    @field_validator("experience", "payout_branch")
    @classmethod
    def _blank(cls, v: str | None) -> str | None:
        return v.strip() or None if v is not None else None

    @field_validator("payout_account_number")
    @classmethod
    def _account(cls, v: str | None) -> str | None:
        if v is None:
            return None
        digits = v.replace(" ", "").replace("-", "")
        if not digits.isalnum():
            raise ValueError("use letters and numbers only")
        return digits

    @field_validator("accept_terms")
    @classmethod
    def _terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError("the teacher terms must be accepted")
        return v


class SubjectRef(BaseModel):
    id: UUID
    name: str


class ApplicationOut(BaseModel):
    id: UUID
    status: ApplicationStatus
    kind: ApplicationKind
    org_name: str
    tenant_slug: str
    subjects: list[SubjectRef]
    experience: str | None
    document_name: str
    payout_bank_name: str
    payout_branch: str | None
    payout_account_name: str
    payout_account_masked: str
    review_note: str | None
    submitted_at: datetime
    reviewed_at: datetime | None


class ApplicationRow(BaseModel):
    """Platform admin list."""

    id: UUID
    status: ApplicationStatus
    kind: ApplicationKind
    org_name: str
    tenant_id: UUID
    tenant_slug: str
    applicant_name: str
    applicant_email: str | None
    applicant_phone: str | None
    submitted_at: datetime


class ApplicationDetail(ApplicationOut):
    tenant_id: UUID
    applicant_name: str
    applicant_email: str | None
    applicant_phone: str | None
    document_type: str
    terms_version: str
    reviewed_by_name: str | None


class DecisionIn(BaseModel):
    decision: Decision
    note: str | None = Field(default=None, max_length=2000)


class AccountNumber(BaseModel):
    account_number: str

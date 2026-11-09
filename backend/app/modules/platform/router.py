from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.integrations.private_storage import PrivateStorage, get_private_storage
from app.integrations.sms import SmsSender, get_sms_sender
from app.modules.auth.dependencies import user_agent
from app.modules.auth.schemas import OtpRequest, OtpRequested
from app.modules.onboarding.schemas import AccountNumber, ApplicationDetail, ApplicationRow, ApplicationStatus, DecisionIn
from app.modules.courses import reviews as course_reviews
from app.modules.courses.schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    CourseDetail,
    CourseStatus,
    HideIn,
    ReviewDecision,
    StaffReview,
    ReviewRow,
    UnpublishIn,
)
from app.modules.platform import applications, audit_log, auth, checkouts, courses, service, subjects, users
from app.modules.platform.auth import Admin, AdminTx, PlatformLogin, PlatformMe, PlatformRefresh, PlatformTokens
from app.modules.platform.schemas import (
    AuditPage,
    CheckoutStatus,
    PayoutCreate,
    PayoutRow,
    PlatformCheckoutDetail,
    PlatformCheckoutPage,
    PlatformPaymentPage,
    RetryResult,
    SignedOut,
    SubjectCreate,
    SubjectRow,
    SubjectUpdate,
    TenantCreate,
    TenantCreated,
    TenantRow,
    TenantStatus,
    TenantUpdate,
    UserDetail,
    UserRow,
)

# EduZone staff only. No tenant host; reachable only from PLATFORM_ALLOWED_CIDRS.
router = APIRouter(prefix="/platform", tags=["platform"])


@router.post("/auth/otp/request", response_model=OtpRequested, status_code=202)
async def request_code(body: OtpRequest, request: Request,
                       sms: Annotated[SmsSender, Depends(get_sms_sender)]) -> OtpRequested:
    return await auth.request_code(body.phone, auth.check_network(request), sms)


@router.post("/auth/login", response_model=PlatformTokens)
async def login(body: PlatformLogin, request: Request) -> PlatformTokens:
    return await auth.login(body, auth.check_network(request), user_agent(request))


@router.post("/auth/refresh", response_model=PlatformTokens)
async def refresh(body: PlatformRefresh, request: Request) -> PlatformTokens:
    return await auth.refresh(body.refresh_token, auth.check_network(request), user_agent(request))


@router.post("/auth/logout", status_code=204)
async def logout(actor: Admin) -> Response:
    await auth.logout(actor)
    return Response(status_code=204)


@router.get("/auth/me", response_model=PlatformMe)
async def me(actor: Admin) -> PlatformMe:
    return await auth.me(actor)


@router.get("/tenants", response_model=list[TenantRow])
async def list_tenants(actor: Admin, session: AdminTx, status: TenantStatus | None = None) -> list[TenantRow]:
    return await service.list_tenants(session, status=status)


@router.post("/tenants", response_model=TenantCreated, status_code=201)
async def create_tenant(body: TenantCreate, actor: Admin, session: AdminTx) -> TenantCreated:
    return await service.create_tenant(session, actor, body)


@router.get("/tenants/{tenant_id}", response_model=TenantRow)
async def get_tenant(tenant_id: UUID, actor: Admin, session: AdminTx) -> TenantRow:
    return await service.get_tenant(session, tenant_id)


@router.patch("/tenants/{tenant_id}", response_model=TenantRow)
async def update_tenant(tenant_id: UUID, body: TenantUpdate, actor: Admin, session: AdminTx) -> TenantRow:
    return await service.update_tenant(session, actor, tenant_id, body)


@router.get("/tenants/{tenant_id}/payouts", response_model=list[PayoutRow])
async def list_payouts(tenant_id: UUID, actor: Admin, session: AdminTx) -> list[PayoutRow]:
    return await service.list_payouts(session, tenant_id)


@router.post("/tenants/{tenant_id}/payouts", response_model=PayoutRow, status_code=201)
async def record_payout(tenant_id: UUID, body: PayoutCreate, actor: Admin, session: AdminTx) -> PayoutRow:
    return await service.record_payout(session, actor, tenant_id, body)


@router.get("/payments", response_model=PlatformPaymentPage)
async def list_payments(
    actor: Admin, session: AdminTx,
    tenant_id: UUID | None = None,
    status: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> PlatformPaymentPage:
    return await service.list_payments(session, tenant_id=tenant_id, status=status, cursor=cursor, limit=limit)


# --- teacher applications (phase 5) ----------------------------------------------------------

@router.get("/applications", response_model=list[ApplicationRow])
async def list_applications(actor: Admin, session: AdminTx,
                            status: ApplicationStatus | None = None) -> list[ApplicationRow]:
    return await applications.list_applications(session, status)


@router.get("/applications/{application_id}", response_model=ApplicationDetail)
async def get_application(application_id: UUID, actor: Admin, session: AdminTx) -> ApplicationDetail:
    return await applications.get_application(session, application_id)


@router.get("/applications/{application_id}/document")
async def application_document(application_id: UUID, actor: Admin, session: AdminTx,
                               storage: Annotated[PrivateStorage, Depends(get_private_storage)]) -> Response:
    content, content_type, name = await applications.document(session, actor, storage, application_id)
    # Shown inline (PDF or photo) but never cached anywhere.
    return Response(content, media_type=content_type, headers={
        "Content-Disposition": f'inline; filename="{name}"', "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff"})


@router.post("/applications/{application_id}/reveal-account", response_model=AccountNumber)
async def reveal_account(application_id: UUID, actor: Admin, session: AdminTx) -> AccountNumber:
    return await applications.reveal_account(session, actor, application_id)


@router.post("/applications/{application_id}/decision", response_model=ApplicationDetail)
async def decide(application_id: UUID, body: DecisionIn, actor: Admin, session: AdminTx) -> ApplicationDetail:
    return await applications.decide(session, actor, application_id, body)


# --- subjects (phase 8) ----------------------------------------------------------------------

@router.get("/subjects", response_model=list[SubjectRow])
async def list_subjects(actor: Admin, session: AdminTx) -> list[SubjectRow]:
    return await subjects.list_subjects(session)


@router.post("/subjects", response_model=SubjectRow, status_code=201)
async def create_subject(body: SubjectCreate, actor: Admin, session: AdminTx) -> SubjectRow:
    return await subjects.create_subject(session, actor, body)


@router.patch("/subjects/{subject_id}", response_model=SubjectRow)
async def update_subject(subject_id: UUID, body: SubjectUpdate, actor: Admin, session: AdminTx) -> SubjectRow:
    return await subjects.update_subject(session, actor, subject_id, body)


# --- users and devices (phase 8) -------------------------------------------------------------

@router.get("/users", response_model=list[UserRow])
async def search_users(actor: Admin, session: AdminTx,
                       q: Annotated[str, Query(min_length=2, max_length=120)]) -> list[UserRow]:
    return await users.search_users(session, q)


@router.get("/users/{user_id}", response_model=UserDetail)
async def get_user(user_id: UUID, actor: Admin, session: AdminTx) -> UserDetail:
    return await users.get_user(session, user_id)


@router.post("/users/{user_id}/sign-out", response_model=SignedOut)
async def sign_out_user(user_id: UUID, actor: Admin, session: AdminTx) -> SignedOut:
    return await users.sign_out_everywhere(session, actor, user_id)


@router.delete("/users/{user_id}/devices/{device_id}", response_model=SignedOut)
async def forget_device(user_id: UUID, device_id: UUID, actor: Admin, session: AdminTx) -> SignedOut:
    return await users.forget_device(session, actor, user_id, device_id)


# --- checkouts (phase 8) ---------------------------------------------------------------------

@router.get("/checkouts", response_model=PlatformCheckoutPage)
async def list_checkouts(
    actor: Admin, session: AdminTx,
    status: CheckoutStatus | None = None,
    stuck: bool = False,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> PlatformCheckoutPage:
    return await checkouts.list_checkouts(session, status=status, stuck=stuck, cursor=cursor, limit=limit)


@router.get("/checkouts/{checkout_id}", response_model=PlatformCheckoutDetail)
async def get_checkout(checkout_id: UUID, actor: Admin, session: AdminTx) -> PlatformCheckoutDetail:
    return await checkouts.get_checkout(session, checkout_id)


@router.post("/checkouts/{checkout_id}/retry", response_model=RetryResult)
async def retry_checkout(checkout_id: UUID, actor: Admin, session: AdminTx) -> RetryResult:
    return await checkouts.retry(session, actor, checkout_id)


# --- audit log (phase 8) ---------------------------------------------------------------------

@router.get("/audit", response_model=AuditPage)
async def list_audit(
    actor: Admin, session: AdminTx,
    tenant_id: UUID | None = None,
    action: Annotated[str | None, Query(max_length=80)] = None,
    actor_id: UUID | None = None,
    entity_id: UUID | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
) -> AuditPage:
    return await audit_log.list_audit(session, tenant_id=tenant_id, action=action, actor_id=actor_id,
                                      entity_id=entity_id, cursor=cursor, limit=limit)


# --- courses: categories and the review queue (docs/COURSES.md, step C1) ---------------------

@router.get("/course-categories", response_model=list[CategoryOut])
async def list_course_categories(actor: Admin, session: AdminTx) -> list[CategoryOut]:
    return await courses.list_categories(session)


@router.post("/course-categories", response_model=CategoryOut, status_code=201)
async def create_course_category(body: CategoryCreate, actor: Admin, session: AdminTx) -> CategoryOut:
    return await courses.create_category(session, actor, body)


@router.patch("/course-categories/{category_id}", response_model=CategoryOut)
async def update_course_category(category_id: int, body: CategoryUpdate, actor: Admin,
                                 session: AdminTx) -> CategoryOut:
    return await courses.update_category(session, actor, category_id, body)


@router.get("/courses", response_model=list[ReviewRow])
async def list_courses(actor: Admin, session: AdminTx, status: CourseStatus = "in_review") -> list[ReviewRow]:
    return await courses.list_reviews(session, status)


@router.get("/courses/{course_id}", response_model=CourseDetail)
async def get_course(course_id: UUID, actor: Admin, session: AdminTx) -> CourseDetail:
    return await courses.get_course(session, course_id)


@router.post("/courses/{course_id}/decision", response_model=CourseDetail)
async def decide_course(course_id: UUID, body: ReviewDecision, actor: Admin, session: AdminTx) -> CourseDetail:
    return await courses.decide(session, actor, course_id, body)


@router.post("/courses/{course_id}/unpublish", response_model=CourseDetail)
async def unpublish_course(course_id: UUID, body: UnpublishIn, actor: Admin, session: AdminTx) -> CourseDetail:
    return await courses.unpublish(session, actor, course_id, body)


# --- course reviews: moderation (step C4) ----------------------------------------------------------

@router.get("/course-reviews", response_model=list[StaffReview])
async def list_course_reviews(actor: Admin, session: AdminTx, status: Literal["visible", "hidden"] | None = None,
                              course_id: UUID | None = None) -> list[StaffReview]:
    return await course_reviews.staff_list(session, status, course_id)


@router.post("/course-reviews/{review_id}/hide", response_model=StaffReview)
async def hide_course_review(review_id: UUID, body: HideIn, actor: Admin, session: AdminTx) -> StaffReview:
    review, tenant_id = await course_reviews.set_visibility(session, review_id, body)
    await service._set_tenant(session, tenant_id)
    await service._audit(session, actor, "platform.course_review.hide", "course_review", review_id,
                         {"reason": body.reason})
    return review


@router.post("/course-reviews/{review_id}/show", response_model=StaffReview)
async def show_course_review(review_id: UUID, actor: Admin, session: AdminTx) -> StaffReview:
    review, tenant_id = await course_reviews.set_visibility(session, review_id, None)
    await service._set_tenant(session, tenant_id)
    await service._audit(session, actor, "platform.course_review.show", "course_review", review_id)
    return review

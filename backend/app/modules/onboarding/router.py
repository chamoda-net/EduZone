from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.integrations.private_storage import PrivateStorage, get_private_storage
from app.modules.auth.dependencies import CurrentUser, client_ip
from app.modules.onboarding import service
from app.modules.onboarding.schemas import ApplicationFields, ApplicationOut

# The signed-in user's own application to teach on EduZone (multipart: fields + the document).
router = APIRouter(prefix="/me/teacher-application", tags=["onboarding"])

Storage = Annotated[PrivateStorage, Depends(get_private_storage)]


def _fields(kind: Annotated[str, Form()], org_name: Annotated[str, Form()],
            subject_ids: Annotated[list[UUID], Form()], payout_bank_name: Annotated[str, Form()],
            payout_account_name: Annotated[str, Form()],
            payout_account_number: Annotated[str | None, Form()] = None,
            accept_terms: Annotated[bool, Form()] = False, experience: Annotated[str | None, Form()] = None,
            payout_branch: Annotated[str | None, Form()] = None) -> ApplicationFields:
    try:
        return ApplicationFields.model_validate({
            "kind": kind, "org_name": org_name, "subject_ids": subject_ids, "experience": experience,
            "payout_bank_name": payout_bank_name, "payout_branch": payout_branch,
            "payout_account_name": payout_account_name,
            "payout_account_number": payout_account_number or None, "accept_terms": accept_terms})
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


Fields = Annotated[ApplicationFields, Depends(_fields)]


async def _read(file: UploadFile) -> service.Document:
    # One byte over the limit is enough to refuse it.
    return service.Document(file.filename or "document", await file.read(service.MAX_DOCUMENT_BYTES + 1))


@router.get("", response_model=ApplicationOut | None)
async def my_application(user: CurrentUser) -> ApplicationOut | None:
    return await service.my_application(user.user_id)


@router.post("", response_model=ApplicationOut, status_code=201)
async def apply(user: CurrentUser, fields: Fields, storage: Storage, request: Request,
                document: Annotated[UploadFile, File()]) -> ApplicationOut:
    return await service.apply(user.user_id, fields, await _read(document), storage, client_ip(request))


@router.put("", response_model=ApplicationOut)
async def resubmit(user: CurrentUser, fields: Fields, storage: Storage, request: Request,
                   document: Annotated[UploadFile | None, File()] = None) -> ApplicationOut:
    doc = await _read(document) if document is not None and document.filename else None
    return await service.resubmit(user.user_id, fields, doc, storage, client_ip(request))

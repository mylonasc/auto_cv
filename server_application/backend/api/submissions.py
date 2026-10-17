from datetime import datetime
from fastapi import APIRouter, Depends
from models.api_models import Submission, SubmissionCreateRequest, SubmissionUpdateRequest
from services.application import ApplicationServices, OperationError
from .dependencies import get_services

router = APIRouter(prefix="/v1/submissions", tags=["Submissions"])


@router.post("/", response_model=Submission)
async def create_submission(request: SubmissionCreateRequest, services: ApplicationServices = Depends(get_services)):
    return services.create_submission(request)


@router.get("/", response_model=list[Submission])
async def list_submissions(services: ApplicationServices = Depends(get_services)):
    return sorted(services.submissions.list(), key=lambda item: item.submitted_at or item.created_at, reverse=True)


@router.get("/{submission_id}", response_model=Submission)
async def get_submission(submission_id: str, services: ApplicationServices = Depends(get_services)):
    result = services.submissions.get(submission_id)
    if result is None:
        raise OperationError(404, "Submission not found")
    return result


@router.put("/{submission_id}", response_model=Submission)
async def update_submission(submission_id: str, request: SubmissionUpdateRequest,
                             services: ApplicationServices = Depends(get_services)):
    def apply(value):
        if request.result is not None:
            value.result = request.result
        if request.notes is not None:
            value.notes = request.notes
        value.updated_at = datetime.now().isoformat()
        return value
    return services.submissions.update(submission_id, apply)


@router.delete("/{submission_id}")
async def delete_submission(submission_id: str, services: ApplicationServices = Depends(get_services)):
    services.submissions.delete(submission_id)
    return {"ok": True, "submission_id": submission_id}

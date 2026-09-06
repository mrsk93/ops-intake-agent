from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ArtifactView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    intake_id: str | None
    artifact_role: str
    display_filename: str
    declared_media_type: str | None
    detected_type: str
    status: str
    content_sha256: str
    size_bytes: int
    external_request_reference: str | None
    amendment_of_artifact_id: str | None
    review_required: bool
    rejection_code: str | None
    rejection_reason: str | None
    created_at: datetime
    accepted_at: datetime | None
    expires_at: datetime | None


class ArtifactUploadResponse(BaseModel):
    artifact: ArtifactView
    duplicate: bool
    duplicate_of_artifact_id: str | None = None

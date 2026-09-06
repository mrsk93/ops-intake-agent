from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=200)


class MembershipView(BaseModel):
    tenant_id: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    memberships: list[MembershipView]


class IdentityView(BaseModel):
    user_id: str
    email: str
    display_name: str
    tenant_id: str
    role: str

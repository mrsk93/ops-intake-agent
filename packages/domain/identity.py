from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    VIEWER = "viewer"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class ActiveStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


@dataclass(frozen=True, slots=True)
class TenantContext:
    user_id: str
    tenant_id: str
    role: Role

    def can_review(self) -> bool:
        return self.role in {Role.REVIEWER, Role.ADMIN}

    def can_administer(self) -> bool:
        return self.role is Role.ADMIN

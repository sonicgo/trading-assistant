from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

# Request Models
class AuthLoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=8)

# Response Models
class AuthTokenResponse(ApiModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = 900 # 15 minutes

class AuthLogoutResponse(ApiModel):
    ok: bool = True

class MeResponse(ApiModel):
    user_id: UUID
    email: str
    is_bootstrap_admin: bool = False


class ErrorEnvelope(ApiModel):
    code: str
    message: str

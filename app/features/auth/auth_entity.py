from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import EmailStr
from pydantic import Field


class AuthLoginRequest(BaseModel):
  """이메일/비밀번호 로그인 요청 스키마 (Domain Entity)"""

  email: EmailStr = Field(..., examples=["user@example.com"])
  password: str = Field(..., min_length=1, examples=["password123"])


class AuthRefreshRequest(BaseModel):
  """리프레시 토큰 기반 갱신 요청 스키마 (Domain Entity)"""

  refresh_token: str = Field(..., min_length=1, examples=["refresh_token"])
  google_refresh_token: str | None = Field(None, examples=["google_refresh_token"])


class UserPublic(BaseModel):
  """응답에 노출되는 공개 사용자 정보 (Domain Entity)"""

  id: str = Field(..., examples=["user_id"])
  email: EmailStr | None = Field(None, examples=["user@example.com"])

  model_config = ConfigDict(from_attributes=True)


class AuthTokenResponse(BaseModel):
  """인증 토큰 응답 스키마 (Domain Entity)"""

  access_token: str
  refresh_token: str
  token_type: str = "bearer"
  expires_in: int | None = None
  user: UserPublic | None = None
  provider_token: str | None = None
  provider_refresh_token: str | None = None
  provider_expires_in: int | None = None

  model_config = ConfigDict(from_attributes=True)


class AuthVerifyResponse(BaseModel):
  """토큰 검증 결과 응답 스키마 (Domain Entity)"""

  valid: bool
  claims: Any | None = None

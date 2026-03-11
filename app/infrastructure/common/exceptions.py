"""인프라 계층 예외 정의 (Infrastructure Layer)
외부 시스템(DB, LLM, API 등)과의 상호작용 중 발생하는 오류를 나타냅니다.
"""


class InfrastructureError(Exception):
  """모든 인프라 예외의 기본 클래스"""

  def __init__(
    self,
    message: str,
    status_code: int | None = None,
    response_body: str | None = None,
  ):
    super().__init__(message)
    self.message = message
    self.status_code = status_code
    self.response_body = response_body


class RepositoryError(InfrastructureError):
  """리포지토리(데이터베이스) 예외"""


# LLM 관련 예외
class LLMError(InfrastructureError):
  """LLM 공통 에러"""


class LLMAuthenticationError(LLMError):
  """LLM 인증 실패 (401)"""


class LLMInvalidRequestError(LLMError):
  """LLM 잘못된 요청 (400)"""


class LLMContextWindowError(LLMInvalidRequestError):
  """LLM 컨텍스트 윈도우 초과 (400 기반)"""


class LLMRateLimitError(LLMError):
  """LLM 요청 제한 초과 (429)"""


class LLMQuotaError(LLMRateLimitError):
  """LLM 쿼터(잔액) 부족 (429 기반)"""


class LLMServerError(LLMError):
  """LLM 서버 에러 (5xx)"""

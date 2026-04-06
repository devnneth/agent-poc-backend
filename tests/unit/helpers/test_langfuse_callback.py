import importlib
from unittest.mock import patch

from app.infrastructure.llm.helpers.langfuse_callback import get_langfuse_callback
from app.infrastructure.llm.helpers.langfuse_callback import validate_langfuse_configuration


# ==================================================================================================
# 테스트용 설정 객체
# --------------------------------------------------------------------------------------------------
# Langfuse 콜백 기능을 테스트하기 위한 더미 설정 클래스입니다
# ==================================================================================================
class DummyConfig:
  # ================================================================================================
  # 초기화
  # ------------------------------------------------------------------------------------------------
  # 더미 설정 객체를 초기화합니다
  # ================================================================================================
  def __init__(
    self,
    public_key: str | None = "public-key",
    secret_key: str | None = "secret-key",
    host: str = "https://cloud.langfuse.com",
  ):
    self.LANGFUSE_PUBLIC_KEY = public_key
    self.LANGFUSE_SECRET_KEY = secret_key
    self.LANGFUSE_HOST = host


# ==================================================================================================
# 인증 키 누락 시 콜백 비활성화 검증
# --------------------------------------------------------------------------------------------------
# 인증 키가 없는 경우 None을 반환하여 통합을 비활성화하는지 확인합니다
# ==================================================================================================
def test_get_langfuse_callback_returns_none_without_keys():
  with patch("app.infrastructure.llm.helpers.langfuse_callback.importlib.import_module") as import_module:
    result = get_langfuse_callback(config=DummyConfig(public_key=None))

  assert result is None
  import_module.assert_not_called()


# ==================================================================================================
# 모듈 누락 시 콜백 비활성화 검증
# --------------------------------------------------------------------------------------------------
# 통합 모듈을 로드할 수 없는 경우 콜백을 비활성화하는지 확인합니다
# ==================================================================================================
def test_get_langfuse_callback_returns_none_when_integration_module_missing():
  with patch(
    "app.infrastructure.llm.helpers.langfuse_callback.importlib.import_module",
    side_effect=ModuleNotFoundError("No module named 'langchain'"),
  ):
    result = get_langfuse_callback(config=DummyConfig())

  assert result is None


# ==================================================================================================
# 콜백 핸들러 생성 검증
# --------------------------------------------------------------------------------------------------
# 통합 모듈 사용 가능 시 Langfuse 핸들러가 정상 생성되는지 확인합니다
# ==================================================================================================
def test_get_langfuse_callback_builds_handler_when_integration_available():
  # ================================================================================================
  # 가짜 핸들러
  # ------------------------------------------------------------------------------------------------
  # Langfuse 테스트를 위한 모킹 핸들러 클래스입니다
  # ================================================================================================
  class FakeHandler:
    # ==============================================================================================
    # 초기화
    # ----------------------------------------------------------------------------------------------
    # 모킹 핸들러를 초기화합니다
    # ==============================================================================================
    def __init__(self, **kwargs):
      self.kwargs = kwargs

  # ================================================================================================
  # 가짜 모듈
  # ------------------------------------------------------------------------------------------------
  # Langfuse 테스트를 위한 모킹 모듈 클래스입니다
  # ================================================================================================
  class FakeModule:
    LangchainCallbackHandler = FakeHandler

  with patch(
    "app.infrastructure.llm.helpers.langfuse_callback.importlib.import_module",
    return_value=FakeModule(),
  ):
    result = get_langfuse_callback(
      config=DummyConfig(),
      tags=["prod"],
      session_id="session-1",
      user_id="user-1",
    )

  assert isinstance(result, FakeHandler)
  assert result.kwargs == {
    "public_key": "public-key",
    "secret_key": "secret-key",
    "host": "https://cloud.langfuse.com",
    "tags": ["prod"],
    "session_id": "session-1",
    "user_id": "user-1",
  }


# ==================================================================================================
# Langfuse 비활성화 시 검증 생략 확인
# --------------------------------------------------------------------------------------------------
# 기능이 꺼져있을 때 설정 검증을 건너뛰는지 확인합니다
# ==================================================================================================
def test_validate_langfuse_configuration_skips_when_langfuse_disabled():
  with patch("app.infrastructure.llm.helpers.langfuse_callback.importlib.import_module") as import_module:
    validate_langfuse_configuration(config=DummyConfig(public_key=None, secret_key=None))

  import_module.assert_not_called()


# ==================================================================================================
# 불완전한 인증 키 거절 검증
# --------------------------------------------------------------------------------------------------
# 필수 인증 키 중 일부가 누락된 경우를 차단하는지 확인합니다
# ==================================================================================================
def test_validate_langfuse_configuration_rejects_partial_keys():
  try:
    validate_langfuse_configuration(config=DummyConfig(secret_key=None))
    raised = None
  except ValueError as e:
    raised = e

  assert raised is not None
  assert "must both be configured" in str(raised)


# ==================================================================================================
# 통합 모듈 누락 허용 검증
# --------------------------------------------------------------------------------------------------
# 모듈이 없어도 서비스 시작은 허용하고 기능만 끄는지 확인합니다
# ==================================================================================================
def test_validate_langfuse_configuration_allows_missing_integration():
  with patch(
    "app.infrastructure.llm.helpers.langfuse_callback.importlib.import_module",
    side_effect=ModuleNotFoundError("No module named 'langchain'"),
  ):
    validate_langfuse_configuration(config=DummyConfig())


# ==================================================================================================
# Langfuse 패키지 호환성 검증
# --------------------------------------------------------------------------------------------------
# 설치된 패키지가 LangChain v1 경로를 지원하는지 확인합니다
# ==================================================================================================
def test_langfuse_langchain_package_supports_langchain_v1():
  module = importlib.import_module("langfuse.callback.langchain")

  assert getattr(module, "LangchainCallbackHandler", None) is not None

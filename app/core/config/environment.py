from functools import lru_cache

from .settings import Settings


class Config:
  """[설정 로직 담당]
  Settings 스키마를 통해 로드된 데이터를 바탕으로,
  애플리케이션에서 실제로 사용할 값을 결정(Computing)하는 로직을 담당합니다.
  """

  def __init__(self):
    self._settings = Settings()

  # 스키마의 기본 값들에 대한 Proxy

  @property
  def PROJECT_NAME(self) -> str:
    return self._settings.PROJECT_NAME

  @property
  def API_V1_STR(self) -> str:
    return self._settings.API_V1_STR

  @property
  def ENVIRONMENT(self) -> str:
    return self._settings.ENVIRONMENT

  @property
  def LOG_LEVEL(self) -> str:
    return (self._settings.LOG_LEVEL or "INFO").upper()

  @property
  def CUSTOM_BASE_URL(self) -> str | None:
    return self._settings.CUSTOM_BASE_URL

  @property
  def MAX_MESSAGE_TOKEN_SIZE(self) -> int | None:
    return self._settings.MAX_MESSAGE_TOKEN_SIZE

  @property
  def CUSTOM_API_KEY(self) -> str | None:
    return self._settings.CUSTOM_API_KEY

  @property
  def CUSTOM_CHAT_URL(self) -> str | None:
    return self._settings.CUSTOM_CHAT_URL

  @property
  def CUSTOM_EMBEDDINGS_URL(self) -> str | None:
    return self._settings.CUSTOM_EMBEDDINGS_URL

  @property
  def CUSTOM_RERANK_URL(self) -> str | None:
    return self._settings.CUSTOM_RERANK_URL

  @property
  def OPENAI_API_KEY(self) -> str | None:
    return self._settings.OPENAI_API_KEY

  @property
  def GEMINI_API_KEY(self) -> str | None:
    return self._settings.GEMINI_API_KEY

  @property
  def ANTHROPIC_API_KEY(self) -> str | None:
    return self._settings.ANTHROPIC_API_KEY

  @property
  def EMBEDDING_ENABLED(self) -> bool:
    return self._settings.EMBEDDING_ENABLED

  @property
  def DEBUG_PROMPT(self) -> bool:
    return self._settings.DEBUG_PROMPT

  @property
  def SUPABASE_SCHEMA(self) -> str:
    if not self._settings.SUPABASE_SCHEMA:
      raise ValueError("SUPABASE_SCHEMA is required")
    return self._settings.SUPABASE_SCHEMA

  @property
  def GOOGLE_CLIENT_ID(self) -> str | None:
    return self._settings.GOOGLE_CLIENT_ID

  @property
  def GOOGLE_CLIENT_SECRET(self) -> str | None:
    return self._settings.GOOGLE_CLIENT_SECRET

  @property
  def LANGFUSE_PUBLIC_KEY(self) -> str | None:
    return self._settings.LANGFUSE_PUBLIC_KEY

  @property
  def LANGFUSE_SECRET_KEY(self) -> str | None:
    return self._settings.LANGFUSE_SECRET_KEY

  @property
  def LANGFUSE_HOST(self) -> str:
    return self._settings.LANGFUSE_HOST

  @property
  def SEARCH_MAX_RESULTS(self) -> int:
    return self._settings.SEARCH_MAX_RESULTS

  @property
  def AGENT_RECURSION_LIMIT(self) -> int:
    return self._settings.AGENT_RECURSION_LIMIT

  @property
  def BACKEND_CORS_ORIGINS(self) -> list[str]:
    origins = self._settings.BACKEND_CORS_ORIGINS
    if origins == "*":
      return ["*"]
    return [origin.strip() for origin in origins.split(",") if origin.strip()]

  # --- 로직이 포함된 속성들 (Computed Properties) ---
  @property
  def SUPABASE_URL(self) -> str:
    """환경(Environment)에 따라 적절한 URL을 결정하여 반환합니다."""
    if self._settings.ENVIRONMENT == "prod":
      if not self._settings.SUPABASE_PROD_URL:
        raise ValueError("Production environment requires SUPABASE_PROD_URL")
      return self._settings.SUPABASE_PROD_URL
    if not self._settings.SUPABASE_API_URL:
      raise ValueError("Supabase API configuration requires SUPABASE_API_URL")
    return self._settings.SUPABASE_API_URL

  @property
  def SUPABASE_KEY(self) -> str:
    """환경(Environment)에 따라 적절한 Key를 결정하여 반환합니다."""
    if self._settings.ENVIRONMENT == "prod":
      if not self._settings.SUPABASE_PROD_KEY:
        raise ValueError("Production environment requires SUPABASE_PROD_KEY")
      return self._settings.SUPABASE_PROD_KEY
    if not self._settings.SUPABASE_SERVICE_ROLE_KEY:
      raise ValueError("Supabase configuration requires SUPABASE_SERVICE_ROLE_KEY")
    return self._settings.SUPABASE_SERVICE_ROLE_KEY

  @property
  def SUPABASE_JWT_SECRET(self) -> str | None:
    return self._settings.SUPABASE_JWT_SECRET

  @property
  def SUPABASE_JWT_PUBLIC_KEY(self) -> str | None:
    return self._settings.SUPABASE_JWT_PUBLIC_KEY

  @property
  def DATABASE_URL(self) -> str:
    """DB 연결 URL을 반환합니다.
    기본적으로 settings.DATABASE_URL을 따르며, 프로토콜 형식을 postgresql://로 일관되게 맞춥니다.
    """
    url = self._settings.DATABASE_URL
    if not url:
      raise ValueError("DATABASE_URL is required but not configured.")

    # SQLAlchemy/psycopg와 호환되도록 프로토콜 강제 변환 (postgres:// -> postgresql://)
    return url.replace("postgres://", "postgresql://")


@lru_cache
def get_config() -> Config:
  return Config()


# 애플리케이션 전역에서 사용할 설정 객체
settings = get_config()

from pydantic import AliasChoices
from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
  """Pydantic-settings를 사용하여 환경 변수를 로드하는 스키마 (Core Layer)"""

  # --- App Configuration ---
  API_V1_STR: str = "/api/v1"
  PROJECT_NAME: str = "AI Assistant PoC API Server"
  ENVIRONMENT: str = "dev"  # dev | prod
  LOG_LEVEL: str = "INFO"
  BACKEND_CORS_ORIGINS: str = "*"

  # --- LLM Configuration ---
  MAX_MESSAGE_TOKEN_SIZE: int | None = None
  CUSTOM_BASE_URL: str | None = None
  CUSTOM_API_KEY: str | None = None
  CUSTOM_CHAT_URL: str | None = None
  CUSTOM_EMBEDDINGS_URL: str | None = None
  CUSTOM_RERANK_URL: str | None = None
  OPENAI_API_KEY: str | None = None
  GEMINI_API_KEY: str | None = None
  ANTHROPIC_API_KEY: str | None = None
  EMBEDDING_ENABLED: bool = False

  # --- Schedule Configuration ---
  SCHEDULE_DEFAULT_DURATION_HOURS: int = 1
  # --- Agent Configuration ---
  AGENT_RECURSION_LIMIT: int = 30
  SEARCH_MAX_RESULTS: int = 10

  # --- Debug Configuration ---
  DEBUG_PROMPT: bool = False

  # --- Supabase Configuration ---
  SUPABASE_API_URL: str | None = None
  SUPABASE_SERVICE_ROLE_KEY: str | None = None

  # --- Supabase Configuration (Prod) ---
  SUPABASE_PROD_URL: str | None = None
  SUPABASE_PROD_KEY: str | None = None

  # --- Database Configuration ---
  DATABASE_URL: str | None = None

  # --- Supabase JWT Secrets ---
  SUPABASE_JWT_SECRET: str | None = None
  SUPABASE_JWT_PUBLIC_KEY: str | None = None

  # --- Schema Configuration ---
  SUPABASE_SCHEMA: str | None = None

  # --- Google OAuth Configuration ---
  GOOGLE_CLIENT_ID: str | None = None
  GOOGLE_CLIENT_SECRET: str | None = None

  # --- Langfuse Configuration ---
  LANGFUSE_PUBLIC_KEY: str | None = None
  LANGFUSE_SECRET_KEY: str | None = None
  LANGFUSE_HOST: str = Field(default="https://cloud.langfuse.com", validation_alias=AliasChoices("LANGFUSE_HOST", "LANGFUSE_BASE_URL"))

  # .env에 서비스별 부가 키가 포함되어 있어도 Settings 스키마 로딩이 깨지지 않도록 무시합니다.
  model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

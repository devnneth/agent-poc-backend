import logging

from langfuse.callback.langchain import LangchainCallbackHandler

from app.core.config.environment import Config

logger = logging.getLogger(__name__)


def get_langfuse_callback(
  config: Config,
  tags: list[str] | None = None,
  session_id: str | None = None,
  user_id: str | None = None,
) -> LangchainCallbackHandler | None:
  """Langfuse 설정이 있는 경우 CallbackHandler를 반환합니다.

  Args:
      config: 환경 설정
      tags: 트레이스 태그
      session_id: 세션 ID (대화 그룹화용)
      user_id: 사용자 ID

  """
  if not config.LANGFUSE_PUBLIC_KEY or not config.LANGFUSE_SECRET_KEY:
    return None

  try:
    handler = LangchainCallbackHandler(
      public_key=config.LANGFUSE_PUBLIC_KEY,
      secret_key=config.LANGFUSE_SECRET_KEY,
      host=config.LANGFUSE_HOST,
      tags=tags,
      session_id=session_id,
      user_id=user_id,
    )
    return handler
  except Exception as e:
    logger.error(f"Failed to initialize Langfuse callback: {e}")
    return None

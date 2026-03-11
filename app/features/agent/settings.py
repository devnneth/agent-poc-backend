from typing import Any
from typing import Literal

from pydantic import BaseModel


class AgentNodeSettings(BaseModel):
  """에이전트 노드별 상세 설정 모델"""

  provider: str
  temperature: float = 0.0
  streaming: bool = True


class AgentModelSettings(BaseModel):
  """전체 에이전트 노드 설정 관리 모델"""

  root_intent_node: AgentNodeSettings
  general_conversation_node: AgentNodeSettings
  classify_schedule_action_node: AgentNodeSettings
  extract_information_node: AgentNodeSettings
  check_information_node: AgentNodeSettings
  intent_shift_node: AgentNodeSettings
  final_response_node: AgentNodeSettings
  user_confirmation_node: AgentNodeSettings
  todo_agent_node: AgentNodeSettings
  memo_agent_node: AgentNodeSettings

  def __getitem__(self, key: str) -> dict[str, Any]:
    """기존 딕셔너리 접근 방식과의 하위 호환성을 위한 메서드"""
    if key not in self.__class__.model_fields:
      raise KeyError(f"Node settings for '{key}' not found.")
    node_config = getattr(self, key)
    if isinstance(node_config, AgentNodeSettings):
      return node_config.model_dump()
    return node_config


class ChatModelConfig(BaseModel):
  """Chat 모델 프로바이더별 모델명 설정"""

  custom: str = "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct-GGUF"
  openai: str = "gpt-4o-mini"
  # openai: str = "gpt-5-nano"
  gemini: str = "gemini-2.5-flash"
  anthropic: str = "claude-3-haiku-20240307"

  def __getitem__(self, key: str) -> str:
    if key not in self.__class__.model_fields:
      raise KeyError(f"Chat model for provider '{key}' not found.")
    return getattr(self, key)


class EmbeddingModelSetting(BaseModel):
  """Embedding 모델 설정 (이름 및 차원수)"""

  name: str
  dimension: int


# 허용된 Embedding 모델 이름 타입 정의
EmbeddingModelName = Literal[
  "EnverLee/bge-m3-korean-Q4_K_M-GGUF",
  "text-embedding-3-small",
  "gemini-embedding-001",
]


class RerankModelConfig(BaseModel):
  """Rerank 모델 프로바이더별 모델명 설정"""

  custom: str = "luckycontrol/bge-reranker-v2-m3-ko-Q4_K_M-GGUF"

  def __getitem__(self, key: str) -> str:
    if key not in self.__class__.model_fields:
      raise KeyError(f"Rerank model for provider '{key}' not found.")
    return getattr(self, key)


class ServiceSettings(BaseModel):
  class ScheduleService(BaseModel):
    embedding: str

  class TodoService(BaseModel):
    embedding: str

  class MemoService(BaseModel):
    embedding: str

  schedule_service: ScheduleService
  todo_service: TodoService
  memo_service: MemoService

  def __getitem__(self, key: str) -> dict[str, Any]:
    """기존 딕셔너리 접근 방식과의 하위 호환성을 위한 메서드"""
    if key not in self.__class__.model_fields:
      raise KeyError(f"Service settings for '{key}' not found.")
    service_config = getattr(self, key)
    if isinstance(service_config, BaseModel):
      return service_config.model_dump()
    return service_config


# Chat Model 설정 인스턴스
CHAT_MODEL_SETTINGS = ChatModelConfig()

# Rerank Model 설정 인스턴스
RERANK_MODEL_SETTINGS = RerankModelConfig()


class EmbeddingModelConfig(BaseModel):
  """Embedding 모델 프로바이더별 모델 설정"""

  custom: EmbeddingModelSetting = EmbeddingModelSetting(name="EnverLee/bge-m3-korean-Q4_K_M-GGUF", dimension=1024)
  openai: EmbeddingModelSetting = EmbeddingModelSetting(name="text-embedding-3-small", dimension=1536)
  gemini: EmbeddingModelSetting = EmbeddingModelSetting(name="gemini-embedding-001", dimension=768)

  def __getitem__(self, key: str) -> EmbeddingModelSetting:
    if key not in self.__class__.model_fields:
      raise KeyError(f"Embedding model for provider '{key}' not found.")
    return getattr(self, key)


# 에이전트 노드 이름과 LLM 설정 매핑 인스턴스 생성
AGENT_MODEL_SETTINGS = AgentModelSettings(
  root_intent_node=AgentNodeSettings(provider="openai", temperature=0, streaming=False),
  general_conversation_node=AgentNodeSettings(provider="openai", temperature=0.7, streaming=True),
  classify_schedule_action_node=AgentNodeSettings(provider="openai", temperature=0, streaming=False),
  extract_information_node=AgentNodeSettings(provider="openai", temperature=0, streaming=False),
  check_information_node=AgentNodeSettings(provider="openai", temperature=0, streaming=False),
  intent_shift_node=AgentNodeSettings(provider="openai", temperature=0, streaming=False),
  final_response_node=AgentNodeSettings(provider="openai", temperature=0.7, streaming=True),
  user_confirmation_node=AgentNodeSettings(provider="openai", temperature=0, streaming=False),
  todo_agent_node=AgentNodeSettings(provider="openai", temperature=0.7, streaming=True),
  memo_agent_node=AgentNodeSettings(provider="openai", temperature=0.7, streaming=True),
)

# 서비스별 모델 설정
SERVICE_SETTINGS = ServiceSettings(
  schedule_service=ServiceSettings.ScheduleService(embedding="openai"),
  todo_service=ServiceSettings.TodoService(embedding="openai"),
  memo_service=ServiceSettings.MemoService(embedding="openai"),
)

# Embedding Model 설정 인스턴스
EMBEDDING_MODEL_SETTINGS = EmbeddingModelConfig()

# 사용 가능한 Embedding 모델 이름 리스트 (런타임 체크용)
AVAILABLE_EMBEDDING_MODELS: list[EmbeddingModelName] = [getattr(EMBEDDING_MODEL_SETTINGS, field_name).name for field_name in EmbeddingModelConfig.model_fields]

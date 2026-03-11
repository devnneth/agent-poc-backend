from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.infrastructure.common.sse_entity import SSECategory
from app.infrastructure.common.sse_entity import SSEPayload
from app.infrastructure.common.sse_entity import SSEStatus
from app.infrastructure.common.sse_entity import SSEType


def format_sse_event(
  type: SSEType | str,
  content: str = "",
  category: SSECategory | str = SSECategory.NONE,
  status: SSEStatus | str = SSEStatus.NONE,
  metadata: dict[str, Any] | None = None,
) -> str:
  """프론트엔드에 스트리밍 응답을 위한 페이로드(SSEPayload)를 전송하기 위한 헬퍼 함수
  데이터를 JSON 문자열로 변환하여 반환합니다. (SSE 표준 'data:' 접두어 제거)
  {json_payload}\n
  """
  if metadata is None:
    metadata = {}

  payload = SSEPayload(
    type=SSEType(type),
    category=SSECategory(category),
    status=SSEStatus(status),
    content=content,
    metadata=metadata,
  )
  return f"{payload.model_dump_json(exclude_none=True)}\n"


async def iter_sse_data(response: httpx.Response) -> AsyncIterator[str]:
  """OpenAI 또는 Gemini 등의 스트리밍 응답에서 한 줄씩 JSON 데이터를 추출합니다."""
  async for line in response.aiter_lines():
    if not line:
      continue
    # 빈 줄이 아니면 그대로 반환 (JSON 문자열)
    yield line

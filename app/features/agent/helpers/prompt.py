from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=128)
def load_prompt(file_path: str | Path) -> str:
  """
  지정된 경로의 프롬프트 텍스트 파일을 읽어 문자열로 반환합니다.
  I/O 최적화를 위해 경로 단위로 메모리에 캐싱합니다.
  """
  path = Path(file_path)
  return path.read_text(encoding="utf-8")

import subprocess
import textwrap


# ==================================================================================================
# 독립 프로세스 Python 실행
# --------------------------------------------------------------------------------------------------
# 별도 프로세스에서 Python 코드를 실행하고 결과를 반환하는 헬퍼 함수
# ==================================================================================================
def _run_python(code: str) -> str:
  result = subprocess.run(  # noqa: S603
    ["./.venv/bin/python", "-c", textwrap.dedent(code)],
    check=True,
    capture_output=True,
    text=True,
  )
  return result.stdout.strip()


# ==================================================================================================
# LLM 제공자 지연 로딩 테스트
# --------------------------------------------------------------------------------------------------
# 모듈 import 시 모든 제공자 구현체가 로드되지 않는지 검증
# ==================================================================================================
def test_llm_provider_factory_does_not_import_all_provider_impls_at_module_import():
  output = _run_python(
    """
    import importlib
    import sys

    importlib.import_module("app.infrastructure.llm.client.llm_provider_factory")

    tracked = [
      "app.infrastructure.llm.providers.anthropic_impl",
      "app.infrastructure.llm.providers.custom_impl",
      "app.infrastructure.llm.providers.gemini_impl",
      "app.infrastructure.llm.providers.openai_impl",
    ]
    loaded = [name for name in tracked if name in sys.modules]
    print(",".join(loaded))
    """
  )

  assert output == ""


# ==================================================================================================
# 채팅 라우터 지연 로딩 테스트
# --------------------------------------------------------------------------------------------------
# 모듈 import 시 에이전트 그래프를 미리 로드하지 않는지 검증
# ==================================================================================================
def test_chat_module_import_does_not_eagerly_load_router_graph():
  output = _run_python(
    """
    import importlib
    import sys

    importlib.import_module("app.api.v1.agent.chat")

    tracked = [
      "app.features.agent.root.root_graph",
      "app.features.agent.memo.memo_agent",
      "app.features.agent.todo.todo_agent",
      "app.features.agent.schedules.schedule_graph",
    ]
    loaded = [name for name in tracked if name in sys.modules]
    print(",".join(loaded))
    """
  )

  assert output == ""

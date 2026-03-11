from app.features.agent.todo.prompts.todo_prompt import SYSTEM_PROMPT


def test_todo_prompt_disallows_verbose_update_examples():
  """수정 추가정보 요청 시 예시 문구를 붙이지 않도록 프롬프트에 명시되어야 한다."""
  assert "예시 JSON, 예시 목록" in SYSTEM_PROMPT
  assert '"한 번에 보내주세요" 같은 부가 안내는 붙이지 마세요.' in SYSTEM_PROMPT


def test_todo_prompt_allows_retry_on_later_turn_after_hitl_reject():
  """HITL 거절 뒤에도 사용자의 명시적 재요청은 다시 처리하도록 프롬프트에 명시되어야 한다."""
  assert "HITL 거절 처리" in SYSTEM_PROMPT
  assert "모델이 자의로 곧바로 반복 호출하지 마세요." in SYSTEM_PROMPT
  assert "사용자가 명시적으로 다시 요청하면" in SYSTEM_PROMPT
  assert "실행 결과가 취소를 의미하면" in SYSTEM_PROMPT


def test_todo_prompt_reuses_previous_update_on_explicit_retry():
  """사용자의 명시적 재시도 요청은 새 수정 정보 요구보다 우선되어야 한다."""
  assert "`다시`, `재시도`, `해야 한다`, `그대로 다시`, `아까대로`" in SYSTEM_PROMPT
  assert "직전 맥락의 수정안을 유지한 채 즉시 `update_todo_tool`을 다시 호출하세요." in SYSTEM_PROMPT
  assert "재시도 의사를 무시하고 같은 정보를 반복해서 다시 요구하지 마세요." in SYSTEM_PROMPT


def test_todo_prompt_calls_update_tool_immediately_with_id_only_retry():
  """ID만으로 수정 재개를 표현해도 추가 질문 없이 바로 도구를 호출해야 한다."""
  assert "`7번 수정`, `7번 바꿔줘`, `7번 다시`" in SYSTEM_PROMPT
  assert "무엇을 바꿀지 다시 묻지 말고" in SYSTEM_PROMPT
  assert "ID만으로 바로 호출" in SYSTEM_PROMPT


def test_todo_prompt_never_requests_update_fields_from_user():
  """수정에서는 사용자가 확인 화면에서 직접 편집하므로 에이전트가 수정값을 다시 묻지 않아야 한다."""
  assert "사용자가 확인 화면에서 값을 직접 편집합니다." in SYSTEM_PROMPT
  assert "수정할 할일 ID만 구별되면 곧바로 `update_todo_tool`을 호출" in SYSTEM_PROMPT
  assert "무엇을 바꿀지 추가로 묻지 마세요." in SYSTEM_PROMPT


def test_todo_prompt_hides_internal_field_names_from_user_messages():
  """사용자 안내에는 JSON이나 내부 필드명을 그대로 노출하지 않아야 한다."""
  assert "`title`, `description`, `status`, `priority`, `project` 같은 내부 필드명" in SYSTEM_PROMPT
  assert "JSON 예시를 그대로 노출하지 마세요." in SYSTEM_PROMPT


def test_todo_prompt_keeps_rejection_followup_short_and_user_friendly():
  """거절 후 후속 안내는 내부 용어 없이 짧게 유지하도록 프롬프트에 명시되어야 한다."""
  assert "거절 후 안내 간소화" in SYSTEM_PROMPT
  assert "내부 용어(HITL 등)" in SYSTEM_PROMPT
  assert "1~2문장으로만 짧게 답하세요." in SYSTEM_PROMPT


def test_todo_prompt_treats_natural_language_phrase_as_title_for_add():
  """'할일에 ... 추가해줘' 형태의 자연어는 전체 작업 문구를 제목으로 간주해야 한다."""
  assert '"할일에 ... 추가해줘"' in SYSTEM_PROMPT
  assert "조사 뒤에 이어지는 핵심 작업 문구 전체를 우선 `title` 후보로 간주" in SYSTEM_PROMPT
  assert '"할일에 저녁에 미용실가서 머리기르기 추가해줘"' in SYSTEM_PROMPT
  assert '"저녁에 미용실가서 머리기르기"' in SYSTEM_PROMPT


def test_todo_prompt_does_not_drop_time_phrase_from_title_without_explicit_due_date():
  """시간 표현이 포함돼도 별도 마감일 요청이 없으면 제목 일부로 유지해야 한다."""
  assert "시간 표현(예: `오늘`, `내일`, `저녁에`, `오후 6시`)" in SYSTEM_PROMPT
  assert "그 표현을 포함한 자연어 구절 전체를 제목으로 받아들여" in SYSTEM_PROMPT

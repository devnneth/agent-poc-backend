from app.api.common.response import fail
from app.api.common.response import ok


def test_ok_response():
  """성공 응답 데이터 형식을 테스트합니다."""
  res = ok({"data": "test"})
  assert res.result == {"data": "test"}
  assert res.message == ""
  assert res.error is False
  assert res.status == 200


def test_ok_response_none():
  """데이터가 없는 성공 응답 형식을 테스트합니다."""
  res = ok(None)
  assert res.result is True
  assert res.message == ""
  assert res.error is False
  assert res.status == 200


def test_ok_response_with_message():
  """성공 응답에서 message 전달을 테스트합니다."""
  res = ok({"data": "test"}, message="success")
  assert res.result == {"data": "test"}
  assert res.message == "success"
  assert res.error is False
  assert res.status == 200


def test_fail_response():
  """실패 응답 데이터 형식을 테스트합니다."""
  res = fail("error message", 400)
  assert res.result is None
  assert res.message == "error message"
  assert res.error is True
  assert res.status == 400

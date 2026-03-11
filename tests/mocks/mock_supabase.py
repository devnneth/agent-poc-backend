from unittest.mock import MagicMock


class MockSupabaseClient:
  """Supabase 클라이언트를 모방하는 모킹 클래스입니다."""

  def __init__(self):
    self.auth = MagicMock()
    self.table = MagicMock()
    self.postgrest = MagicMock()

  def from_(self, table_name: str):
    """table() 메서드와 동일한 역할을 수행합니다."""
    return self.table(table_name)


def get_mock_supabase_client():
  """모킹된 Supabase 클라이언트 인스턴스를 생성하여 반환합니다."""
  return MockSupabaseClient()

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import text

from app.infrastructure.models.knowledge_model import KnowledgeChunksModel
from app.infrastructure.models.knowledge_model import KnowledgesModel
from app.infrastructure.models.knowledge_model import KnowledgeSourcesModel
from app.infrastructure.models.knowledge_model import ProcessingStatus
from app.infrastructure.models.knowledge_model import SourceType

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "data-transfer" / "transfer_knowledge_to_prod.py"
MODULE_NAME = "transfer_knowledge_to_prod"


# ==================================================================================================
# 스크립트 모듈 로드
# --------------------------------------------------------------------------------------------------
# 테스트 대상 스크립트를 동적으로 로드합니다
# ==================================================================================================
def _load_script_module():
  existing_module = sys.modules.get(MODULE_NAME)
  if existing_module is not None:
    return existing_module

  spec = importlib.util.spec_from_file_location(MODULE_NAME, SCRIPT_PATH)
  assert spec is not None
  assert spec.loader is not None

  module = importlib.util.module_from_spec(spec)
  sys.modules[MODULE_NAME] = module
  spec.loader.exec_module(module)
  return module


# ==================================================================================================
# 모델 복제 검증
# --------------------------------------------------------------------------------------------------
# 모델 복제 시 식별자는 유지하고 가변값은 올바르게 복사되는지 확인합니다
# ==================================================================================================
def test_clone_models_preserve_identity_and_copy_mutable_values():
  module = _load_script_module()
  created_at = datetime.now(UTC)
  knowledge_id = uuid4()
  source_id = uuid4()
  chunk_id = uuid4()
  target_user_id = "prod-user-1"

  knowledge = KnowledgesModel(
    id=knowledge_id,
    user_id="user-1",
    title="제품 문서",
    description="설명",
    is_rag_enabled=False,
    created_at=created_at,
    updated_at=created_at,
  )
  source = KnowledgeSourcesModel(
    id=source_id,
    knowledge_id=knowledge_id,
    user_id="user-1",
    source_type=SourceType.FILE,
    display_name="manual.pdf",
    storage_path="user-1/manual.pdf",
    file_size=123,
    token_count=45,
    mime_type="application/pdf",
    is_rag_enabled=False,
    processing_status=ProcessingStatus.DONE,
    source_metadata={"pages": [1, 2]},
    created_at=created_at,
    updated_at=created_at,
  )
  chunk = KnowledgeChunksModel(
    id=chunk_id,
    source_id=source_id,
    user_id="user-1",
    chunk_index=0,
    chunk_content="첫 문단",
    embedding=[0.1, 0.2, 0.3],
    chunk_metadata={"page": 1, "tags": ["intro"]},
    created_at=created_at,
  )

  copied_knowledge = module.clone_knowledge_model(knowledge, target_user_id)
  copied_source = module.clone_source_model(source, target_user_id)
  copied_chunk = module.clone_chunk_model(chunk, target_user_id)

  assert copied_knowledge.id == knowledge.id
  assert copied_knowledge.user_id == target_user_id
  assert copied_knowledge.title == knowledge.title
  assert copied_knowledge.is_rag_enabled is False
  assert copied_source.id == source.id
  assert copied_source.user_id == target_user_id
  assert copied_source.knowledge_id == source.knowledge_id
  assert copied_source.is_rag_enabled is False
  assert copied_source.source_metadata == source.source_metadata
  assert copied_source.source_metadata is not source.source_metadata
  assert copied_chunk.id == chunk.id
  assert copied_chunk.user_id == target_user_id
  assert copied_chunk.source_id == chunk.source_id
  assert copied_chunk.embedding == chunk.embedding
  assert copied_chunk.embedding is not chunk.embedding
  assert copied_chunk.chunk_metadata == chunk.chunk_metadata
  assert copied_chunk.chunk_metadata is not chunk.chunk_metadata


# ==================================================================================================
# 대상 사용자 식별자 조회 검증
# --------------------------------------------------------------------------------------------------
# 이메일을 기반으로 인증 사용자 ID를 정확히 조회하는지 확인합니다
# ==================================================================================================
def test_resolve_target_user_id_loads_auth_user_by_email():
  module = _load_script_module()
  session = MagicMock()
  connection = session.connection.return_value
  connection.execute.return_value.scalar_one_or_none.return_value = "prod-user-1"

  result = module.resolve_target_user_id(session, "lastsky@gmail.com")

  assert result == "prod-user-1"
  statement = connection.execute.call_args.args[0]
  params = connection.execute.call_args.args[1]
  assert str(statement) == str(text("SELECT id::text FROM auth.users WHERE email = :email LIMIT 1"))
  assert params == {"email": "lastsky@gmail.com"}


# ==================================================================================================
# DB 엔진 생성 설정 검증
# --------------------------------------------------------------------------------------------------
# 커넥션 풀러 사용을 위해 Prepared Statement가 꺼진 엔진이 생성되는지 확인합니다
# ==================================================================================================
def test_create_db_engine_disables_prepared_statements_for_pooler():
  module = _load_script_module()
  config = module.ScriptDbConfig(
    env_file=Path(".env.prod"),
    database_url="postgresql://user:pass@example.com:6543/postgres",
    schema="public",
  )

  with patch.object(module, "create_engine", return_value=MagicMock()) as create_engine_mock:
    module.create_db_engine(config)

  kwargs = create_engine_mock.call_args.kwargs
  assert kwargs["connect_args"] == {
    "options": "-c search_path=public",
    "prepare_threshold": None,
  }


# ==================================================================================================
# 지식 이관 로직 검증
# --------------------------------------------------------------------------------------------------
# 기존 제목은 건너뛰고 새로운 번들만 정상적으로 복사하는지 확인합니다
# ==================================================================================================
def test_transfer_knowledges_skips_existing_titles_and_copies_new_bundle():
  module = _load_script_module()
  created_at = datetime.now(UTC)
  target_user_id = "prod-user-1"

  duplicated_knowledge = KnowledgesModel(
    id=uuid4(),
    user_id="user-1",
    title="이미 있는 문서",
    description="중복",
    created_at=created_at,
    updated_at=created_at,
  )
  new_knowledge = KnowledgesModel(
    id=uuid4(),
    user_id="user-2",
    title="새 문서",
    description="신규",
    is_rag_enabled=False,
    created_at=created_at,
    updated_at=created_at,
  )
  new_source = KnowledgeSourcesModel(
    id=uuid4(),
    knowledge_id=new_knowledge.id,
    user_id="user-2",
    source_type=SourceType.FILE,
    display_name="new.pdf",
    storage_path="user-2/new.pdf",
    file_size=321,
    token_count=30,
    mime_type="application/pdf",
    is_rag_enabled=False,
    processing_status=ProcessingStatus.DONE,
    created_at=created_at,
    updated_at=created_at,
  )
  new_chunk = KnowledgeChunksModel(
    id=uuid4(),
    source_id=new_source.id,
    user_id="user-2",
    chunk_index=0,
    chunk_content="신규 청크",
    embedding=[0.4, 0.5],
    chunk_metadata={"page": 2},
    created_at=created_at,
  )

  source_session = MagicMock()
  target_session = MagicMock()

  with (
    patch.object(
      module,
      "load_active_knowledges",
      return_value=[duplicated_knowledge, new_knowledge],
    ),
    patch.object(module, "load_existing_titles", return_value={"이미 있는 문서"}),
    patch.object(module, "resolve_target_user_id", return_value=target_user_id) as resolve_target_user_id,
    patch.object(module, "load_active_sources", return_value=[new_source]) as load_sources,
    patch.object(
      module,
      "load_chunks_by_source",
      return_value={new_source.id: [new_chunk]},
    ) as load_chunks,
  ):
    summary = module.transfer_knowledges(source_session, target_session)

  assert summary.transferred_knowledges == 1
  assert summary.skipped_knowledges == 1
  assert summary.transferred_sources == 1
  assert summary.transferred_chunks == 1
  assert target_session.flush.call_count == 2
  assert target_session.commit.call_count == 1
  assert target_session.rollback.call_count == 0
  assert target_session.add.call_count == 3

  added_models = [call.args[0] for call in target_session.add.call_args_list]
  assert [model.__class__.__name__ for model in added_models] == [
    "KnowledgesModel",
    "KnowledgeSourcesModel",
    "KnowledgeChunksModel",
  ]
  assert added_models[0].title == "새 문서"
  assert added_models[0].user_id == target_user_id
  assert added_models[0].is_rag_enabled is False
  assert added_models[1].knowledge_id == new_knowledge.id
  assert added_models[1].user_id == target_user_id
  assert added_models[1].is_rag_enabled is False
  assert added_models[2].source_id == new_source.id
  assert added_models[2].user_id == target_user_id
  assert [method[0] for method in target_session.method_calls] == [
    "add",
    "flush",
    "add",
    "flush",
    "add",
    "commit",
  ]

  resolve_target_user_id.assert_called_once_with(target_session, module.TARGET_USER_EMAIL)
  load_sources.assert_called_once_with(source_session, new_knowledge.id)
  load_chunks.assert_called_once_with(source_session, [new_source.id])

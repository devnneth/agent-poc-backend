from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.features.knowledge.processing.basic_pipeline.knowledge_parser_adapter import KnowledgeParserAdapter


# ==================================================================================================
# 중첩 디렉토리 산출물 읽기 테스트
# --------------------------------------------------------------------------------------------------
# 모듈 호출 후 중첩된 디렉토리에 생성된 산출물을 찾아 읽는지 검증
# ==================================================================================================
def test_knowledge_parser_adapter_reads_nested_outputs(tmp_path, monkeypatch):
  input_path = tmp_path / "sample.pdf"
  input_path.write_bytes(b"pdf")
  output_dir = tmp_path / "out"
  captured: dict[str, object] = {}

  # ------------------------------------------------------------------------------------------------
  # 가짜 변환 함수
  # ------------------------------------------------------------------------------------------------
  def fake_convert(*, input_path: str, output_dir: str, format: list[str], quiet: bool, **kwargs: object) -> None:
    captured["input_path"] = input_path
    captured["output_dir"] = output_dir
    captured["format"] = format
    captured["quiet"] = quiet
    captured.update(kwargs)
    nested_dir = Path(output_dir) / "nested"
    nested_dir.mkdir(parents=True, exist_ok=True)
    (nested_dir / "sample.md").write_text("# 제목", encoding="utf-8")
    (nested_dir / "sample.json").write_text(json.dumps({"pages": [{"number": 1}]}), encoding="utf-8")

  monkeypatch.setattr(
    "app.features.knowledge.processing.basic_pipeline.knowledge_parser_adapter.shutil.which",
    lambda command: "/usr/bin/java" if command == "java" else None,
  )
  monkeypatch.setattr(
    "app.features.knowledge.processing.basic_pipeline.knowledge_parser_adapter.opendataloader_pdf_convert",
    fake_convert,
  )

  adapter = KnowledgeParserAdapter()
  parsed_document = adapter.convert(input_path, output_dir)

  assert captured == {
    "input_path": str(input_path),
    "output_dir": str(output_dir),
    "format": ["json", "markdown"],
    "quiet": True,
    "use_struct_tree": True,
  }
  assert parsed_document.markdown == "# 제목"
  assert parsed_document.document_json == {"pages": [{"number": 1}]}


# ==================================================================================================
# Markdown 확장자 처리 테스트
# --------------------------------------------------------------------------------------------------
# .markdown 확장자를 가진 산출물도 정상적으로 처리하는지 검증
# ==================================================================================================
def test_knowledge_parser_adapter_reads_markdown_extension_output(tmp_path, monkeypatch):
  input_path = tmp_path / "sample.pdf"
  input_path.write_bytes(b"pdf")
  output_dir = tmp_path / "out"

  # ------------------------------------------------------------------------------------------------
  # 가짜 Markdown 변환 함수
  # ------------------------------------------------------------------------------------------------
  def fake_convert(*, input_path: str, output_dir: str, format: list[str], quiet: bool, **kwargs: object) -> None:
    del input_path, format, quiet, kwargs
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    (Path(output_dir) / "sample.markdown").write_text("# 제목", encoding="utf-8")
    (Path(output_dir) / "sample.json").write_text(json.dumps({"pages": [{"number": 1}]}), encoding="utf-8")

  monkeypatch.setattr(
    "app.features.knowledge.processing.basic_pipeline.knowledge_parser_adapter.shutil.which",
    lambda command: "/usr/bin/java" if command == "java" else None,
  )
  monkeypatch.setattr(
    "app.features.knowledge.processing.basic_pipeline.knowledge_parser_adapter.opendataloader_pdf_convert",
    fake_convert,
  )

  adapter = KnowledgeParserAdapter()
  parsed_document = adapter.convert(input_path, output_dir)

  assert parsed_document.markdown == "# 제목"
  assert parsed_document.document_json == {"pages": [{"number": 1}]}


# ==================================================================================================
# 필수 산출물 누락 예외 테스트
# --------------------------------------------------------------------------------------------------
# 필수 JSON 산출물이 없을 때 명시적인 예외를 발생하는지 검증
# ==================================================================================================
def test_knowledge_parser_adapter_raises_when_json_output_missing(tmp_path, monkeypatch):
  input_path = tmp_path / "sample.pdf"
  input_path.write_bytes(b"pdf")
  output_dir = tmp_path / "out"

  # ------------------------------------------------------------------------------------------------
  # 산출물 누락 모의 함수
  # ------------------------------------------------------------------------------------------------
  def fake_convert(*, input_path: str, output_dir: str, format: list[str], quiet: bool, **kwargs: object) -> None:
    del input_path, format, quiet, kwargs
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    (Path(output_dir) / "sample.md").write_text("# 제목", encoding="utf-8")

  monkeypatch.setattr(
    "app.features.knowledge.processing.basic_pipeline.knowledge_parser_adapter.shutil.which",
    lambda command: "/usr/bin/java" if command == "java" else None,
  )
  monkeypatch.setattr(
    "app.features.knowledge.processing.basic_pipeline.knowledge_parser_adapter.opendataloader_pdf_convert",
    fake_convert,
  )

  adapter = KnowledgeParserAdapter()

  with pytest.raises(ValueError, match=r"\.json"):
    adapter.convert(input_path, output_dir)

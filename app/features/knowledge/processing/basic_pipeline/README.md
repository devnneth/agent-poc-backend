# basic_pipeline

현재 워커의 기본 처리 경로입니다.

이 파이프라인은 원본 파일을 읽어 Markdown 기반 청크를 만들고, 공통 계층을 통해 임베딩과 `knowledge_chunks` 저장까지 끝냅니다.

## 처리 흐름

1. 워커가 `KnowledgeProcessingService.process_source()`를 호출합니다.
2. 소스 레코드를 조회하고 처리 시작 로그를 남깁니다.
3. 파일 경로를 확인한 뒤 확장자에 따라 분기합니다.
4. `.md`, `.txt`는 파일 내용을 직접 읽고 이미지 링크를 정규화합니다.
5. `.pdf`는 `KnowledgeParserAdapter`가 `opendataloader-pdf`를 호출해 `ParsedDocument`를 만듭니다.
6. `KnowledgeMetadataService`가 Markdown과 JSON을 바탕으로 `source_metadata`를 생성합니다.
7. `MarkdownChunkingService`가 Markdown heading 기준으로 `DocumentChunk` 목록을 만듭니다.
8. `KnowledgeChunkPersistenceService`가 청크 본문을 배치 임베딩하고 기존 `knowledge_chunks`를 교체 저장합니다.
9. `knowledge_sources`의 `token_count`, `source_metadata`, `processing_status`, 완료 시각을 갱신하고 commit 합니다.
10. 예외가 나면 rollback 후 `processing_status=ERROR`로 기록합니다.

## 책임 경계

- 이 디렉토리 책임:
  - 파일 파싱
  - Markdown 기반 청킹
  - `ParsedDocument` 생성
- 공통 계층 책임:
  - [knowledge_entity.py](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/common/knowledge_entity.py)
  - [metadata_service.py](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/common/metadata_service.py)
  - [chunk_persistence_service.py](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/common/chunk_persistence_service.py)

즉, `basic_pipeline`은 "청크를 만들기까지"에 집중하고, 임베딩과 DB 저장은 공통 서비스에 위임합니다.

## 주요 파일

- [processing_service.py](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/processing/basic_pipeline/processing_service.py)
  - 워커에서 직접 호출되는 진입점
- [knowledge_parser_adapter.py](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/processing/basic_pipeline/knowledge_parser_adapter.py)
  - PDF -> Markdown/JSON 변환
- [chunking_service.py](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/processing/basic_pipeline/chunking_service.py)
  - Markdown -> `DocumentChunk` 목록 변환

## 입력과 출력

- 입력:
  - `knowledge_sources` 레코드
  - 업로드 파일(`UPLOAD_DIR`)
- 파이프라인 내부 산출물:
  - `ParsedDocument`
  - `list[DocumentChunk]`
- 최종 반영:
  - `knowledge_sources.source_metadata`
  - `knowledge_sources.token_count`
  - `knowledge_sources.processing_status`
  - `knowledge_chunks`

## 현재 제약

- PDF 파싱 엔진은 `opendataloader-pdf`에 고정되어 있습니다.
- 청킹은 Markdown heading 구조 중심입니다.
- 청크 메타데이터는 `heading_path`, `page_range`, `content_type` 형태를 기본으로 사용합니다.

## odlh_pipeline와의 관계

현재 `odlh_pipeline`도 같은 공통 계층을 사용합니다.
두 파이프라인은 청킹 방식은 다르지만, 이후 임베딩과 `knowledge_chunks` 저장은 동일한 공통 서비스로 처리합니다.

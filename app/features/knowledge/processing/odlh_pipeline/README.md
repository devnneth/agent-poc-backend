# odlh_pipeline

구조 보존형 PDF 처리 파이프라인입니다.

이 파이프라인은 PDF를 JSON/Markdown으로 변환하고, 문서 구조를 분석해 JSON 청크 파일을 생성한 뒤 공통 계층으로 임베딩과 `knowledge_chunks` 저장까지 마칩니다.
현재 워커에서 `--pipeline odlh`로 선택할 수 있는 처리 경로입니다.

## 처리 흐름

1. 워커가 [processing_service.py](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/processing/odlh_pipeline/processing_service.py)를 호출합니다.
2. 소스 레코드를 조회하고 업로드 파일 경로를 확인합니다.
3. `.pdf`는 `ParseService -> AnalysisService -> ChunkService` 순서로 odlh 산출물을 만듭니다.
4. `.md`, `.txt`는 공통 텍스트 읽기 경로로 Markdown을 정규화한 뒤 `AnalysisService`와 `TextChunkExportService`로 odlh 산출물을 만듭니다.
5. `ChunkFileLoaderService`가 `chunks/*.json`을 순서대로 읽어 `DocumentChunk` 목록으로 변환합니다.
6. 공통 [metadata_service.py](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/common/metadata_service.py)가 `source_metadata`를 생성합니다.
7. 공통 [chunk_persistence_service.py](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/common/chunk_persistence_service.py)가 임베딩과 `knowledge_chunks` 교체 저장을 수행합니다.
8. `knowledge_sources`의 `token_count`, `source_metadata`, `processing_status`를 갱신하고 commit 합니다.
9. 성공 후 `CleanupService.remove_intermediate_artifacts()`가 중간 `.json`, `.md` 산출물을 제거합니다.

## 핵심 특징

- 단순 heading split이 아니라 문서 구조 품질을 먼저 분석합니다.
- 짧은 인접 섹션을 병합합니다.
- `hybrid`, `semantic`, `auto` 전략을 지원합니다.
- PDF와 함께 `.md`, `.txt`도 같은 odlh 모듈 안에서 처리합니다.
- 최종 저장은 공통 계층을 사용하므로 `basic_pipeline`과 DB 적재 방식이 같습니다.

## 주요 파일

- [processing_service.py](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/processing/odlh_pipeline/processing_service.py)
  - 워커에서 직접 호출되는 odlh 진입점
- [services/parse_service.py](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/processing/odlh_pipeline/services/parse_service.py)
  - PDF -> JSON/Markdown 변환
- [services/analysis_service.py](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/processing/odlh_pipeline/services/analysis_service.py)
  - Markdown 구조 분석 및 전략 선택
- [services/chunk_service.py](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/processing/odlh_pipeline/services/chunk_service.py)
  - 섹션 수집, 병합, Markdown/JSON 청크 파일 생성
- [services/text_chunk_export_service.py](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/processing/odlh_pipeline/services/text_chunk_export_service.py)
  - Markdown/TXT 입력을 odlh 청크 파일 구조로 내보냄
- [services/chunk_file_loader_service.py](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/processing/odlh_pipeline/services/chunk_file_loader_service.py)
  - `chunks/*.json` -> `DocumentChunk` 목록 로드
- [core](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/processing/odlh_pipeline/core)
  - heading 추론, Markdown 렌더링, chunker, path/progress 유틸리티
- [models/models.py](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/processing/odlh_pipeline/models/models.py)
  - `PipelinePaths`, `ChunkingStrategy` 등 전용 모델
- [config/contants.py](/Users/develosopher/projects/gplanner-ppa-api/app/features/knowledge/processing/odlh_pipeline/config/contants.py)
  - 파이프라인 전용 상수

## 출력 구조

기본적으로 아래와 같은 산출물을 만듭니다.

```text
<output_dir>/
  progress.json
  chunking_analysis.json
  markdowns/
    _manifest.json
    *.md
  chunks/
    _manifest.json
    *.json
  images/
    *
```

JSON 청크 파일은 대략 아래 계약을 가집니다.

```json
{
  "content": "...",
  "metadata": {
    "chunking_strategy": "hybrid",
    "title": "...",
    "navigation": "...",
    "images": ["..."]
  }
}
```

## 현재 프로젝트에서의 의미

이 파이프라인은 현재 저장소 기준으로 "고품질 청크 산출물 생성 + 공통 임베딩/DB 저장 연결"까지 끝내는 워커 모듈입니다.
즉, `odlh_pipeline`의 역할은 청크 품질은 자체적으로 책임지고, 저장 일관성은 공통 계층에 맡기는 구조입니다.

## 현재 제약

- PDF 처리는 hybrid backend가 떠 있어야 합니다.
- 배포 환경에서는 워커와 별도로 [rag-backend.sh](/Users/develosopher/projects/gplanner-ppa-api/scripts/rag-backend.sh)를 운영해야 합니다.
- 산출물 기반 중간 디버깅이 필요하면 cleanup 정책을 별도로 조정해야 합니다.

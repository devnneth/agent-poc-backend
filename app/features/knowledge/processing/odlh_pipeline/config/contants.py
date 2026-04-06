"""
프로젝트 전반에서 공유하는 상수 모음.
"""

import re
from typing import Final

# ==================================================================================================
# 공통 I/O / 인코딩
# --------------------------------------------------------------------------------------------------
# 파일 입출력과 JSON 직렬화에서 공통으로 사용하는 기본값
# ==================================================================================================
DEFAULT_ENCODING_NAME: Final = "cl100k_base"
TEXT_FILE_ENCODING: Final = "utf-8"
JSON_INDENT: Final = 2


# ==================================================================================================
# 경로 / 파일명
# --------------------------------------------------------------------------------------------------
# 파이프라인 산출물 디렉토리와 공통 파일명 규칙
# ==================================================================================================
DEFAULT_OUTPUT_DIRNAME: Final = "output"
PROGRESS_FILENAME: Final = "progress.json"
CHUNKING_ANALYSIS_REPORT_FILENAME: Final = "chunking_analysis.json"
MANIFEST_FILENAME: Final = "_manifest.json"
MARKDOWN_OUTPUT_DIRNAME: Final = "markdowns"
JSON_CHUNK_OUTPUT_DIRNAME: Final = "chunks"
IMAGE_OUTPUT_DIRNAME: Final = "images"
RAW_IMAGE_DIR_SUFFIX: Final = "_images"
LEGACY_CHUNK_DIR_SUFFIX: Final = "_chunks"
DEFAULT_UNTITLED_TITLE: Final = "untitled"


# ==================================================================================================
# CLI / 환경 변수
# --------------------------------------------------------------------------------------------------
# 커맨드라인 진입점과 환경 변수에서 사용하는 고정 문자열
# ==================================================================================================
CLI_DESCRIPTION: Final = "PDF to Markdown Pipeline"
CLI_PDF_PATH_HELP: Final = "Path to the source PDF file"
CLI_ENCODING_HELP: Final = "Tokenizer encoding name"
CLI_OUTPUT_DIR_HELP: Final = "Base output directory"
CLI_CHUNK_SIZE_HELP: Final = "Chunk size for markdown splitting"
CLI_CHUNK_OVERLAP_HELP: Final = "Chunk overlap for markdown splitting"
CLI_BACKEND_URL_HELP: Final = "Backend URL (overrides env PDF_BACKEND_URL)"
CLI_CHUNKING_STRATEGY_HELP: Final = "Chunking strategy selection: auto, hybrid, semantic"
PDF_BACKEND_URL_ENV_VAR: Final = "PDF_BACKEND_URL"
OPENAI_API_KEY_ENV_VAR: Final = "OPENAI_API_KEY"
OPENAI_EMBEDDING_MODEL_ENV_VAR: Final = "OPENAI_EMBEDDING_MODEL"


# ==================================================================================================
# 백엔드 연결 설정
# --------------------------------------------------------------------------------------------------
# Docling 백엔드 연결과 헬스체크에 필요한 기본값
# ==================================================================================================
DEFAULT_HYBRID_BACKEND_URL: Final = "http://127.0.0.1:5002"
BACKEND_HEALTHCHECK_PATH: Final = "/health"
BACKEND_NOT_RUNNING_MESSAGE: Final = "백엔드 접근에 실패했습니다. 지정된 백엔드 서버가 실행 중인지 확인해 주세요."
EMBEDDING_CONFIG_MISSING_MESSAGE: Final = "의미 기반 청킹을 위해 OPENAI_API_KEY 환경 변수가 필요합니다."
BACKEND_REQUEST_TIMEOUT_SECONDS: Final = 2.0
SUPPORTED_BACKEND_URL_SCHEMES: Final[tuple[str, ...]] = ("http://", "https://")
HTTP_SUCCESS_STATUS_MIN: Final = 200
HTTP_SUCCESS_STATUS_MAX: Final = 300


# ==================================================================================================
# OpenDataLoader 변환 옵션
# --------------------------------------------------------------------------------------------------
# PDF -> JSON/Markdown 변환 시 고정으로 사용하는 라이브러리 옵션
# ==================================================================================================
OPENDATALOADER_FORMAT: Final = "json,markdown"
OPENDATALOADER_TABLE_METHOD: Final = "cluster"
OPENDATALOADER_HYBRID_ENGINE: Final = "docling-fast"
OPENDATALOADER_HYBRID_MODE: Final = "full"
OPENDATALOADER_SANITIZE: Final = True
OPENDATALOADER_USE_STRUCT_TREE: Final = True
OPENDATALOADER_QUIET: Final = True


# ==================================================================================================
# OpenAI 임베딩 설정
# --------------------------------------------------------------------------------------------------
# SemanticChunker에 주입할 OpenAI 임베딩 기본 모델
# ==================================================================================================
DEFAULT_OPENAI_EMBEDDING_MODEL: Final = "text-embedding-3-small"


# ==================================================================================================
# 청킹 / 분석 기본 설정
# --------------------------------------------------------------------------------------------------
# 전체 파이프라인에서 공유하는 청킹 기본값과 임계값
# ==================================================================================================
BOOK_START_ID: Final = 0
DEFAULT_CHUNK_SIZE: Final = 500
DEFAULT_CHUNK_OVERLAP: Final = 50
DEFAULT_MIN_CHUNK_LENGTH: Final = 15
MAX_HEADING_TEXT_LENGTH: Final = 200
MIN_SECTION_SIGNAL_LENGTH: Final = 80
MIN_MERGED_CHUNK_LENGTH: Final = 300
LARGEST_SECTION_LIMIT: Final = 5
MIN_MARKDOWN_HEADING_COUNT_FOR_HYBRID: Final = 3
MIN_SECTION_FIT_RATE_FOR_HYBRID: Final = 0.55
MAX_OVERSIZE_SECTION_RATE_FOR_HYBRID: Final = 0.2
MAX_P90_SECTION_TO_CHUNK_SIZE_RATIO: Final = 1.8
MAX_HEADERLESS_RUN_TO_CHUNK_SIZE_RATIO: Final = 2.5
HEADER_FIT_LOWER_BOUND_RATIO: Final = 0.35
HEADER_FIT_UPPER_BOUND_RATIO: Final = 1.5
HEADER_OVERSIZE_RATIO: Final = 2.0
HEADER_UNDERSIZE_RATIO: Final = 0.2
MEDIAN_PERCENTILE: Final = 0.5
P90_PERCENTILE: Final = 0.9
NO_HEADING_PLACEHOLDER: Final = "(no heading)"


# ==================================================================================================
# Markdown / heading 처리
# --------------------------------------------------------------------------------------------------
# Markdown 구문, heading 파싱, breadcrumb 표현에 사용하는 공통 규칙
# ==================================================================================================
MIN_MARKDOWN_HEADING_LEVEL: Final = 1
MAX_MARKDOWN_HEADING_LEVEL: Final = 6
DEFAULT_RENDER_HEADING_LEVEL: Final = 1
FENCED_CODE_BLOCK_MARKER: Final = "```"
BREADCRUMB_PREFIX: Final = "> 경로:"
BREADCRUMB_SEPARATOR: Final = " > "
IMAGE_PLACEHOLDER_TEMPLATE: Final = "[IMAGE_{index}]"
SEMANTIC_SENTENCE_SPLIT_REGEX: Final = r"(?<=[.!?。！？])\s+|\n{2,}"
BOOK_HEADING_LEVELS: Final[tuple[str, ...]] = ("Subtitle", "Doctitle")
HEADERS_TO_SPLIT_ON: Final[tuple[tuple[str, str], ...]] = (
  ("#", "title"),
  ("##", "title"),
  ("###", "title"),
  ("####", "title"),
  ("#####", "title"),
  ("######", "title"),
)


# ==================================================================================================
# 렌더링 / 메타데이터 키
# --------------------------------------------------------------------------------------------------
# Markdown 렌더링과 청크 JSON 메타데이터에서 공유하는 식별자
# ==================================================================================================
NODE_TYPE_HEADING: Final = "heading"
NODE_TYPE_PARAGRAPH: Final = "paragraph"
NODE_TYPE_CAPTION: Final = "caption"
NODE_TYPE_IMAGE: Final = "image"
NODE_TYPE_LIST: Final = "list"
NODE_TYPE_LIST_ITEM: Final = "list item"
NODE_TYPE_FOOTER: Final = "footer"
LIST_INDENT_UNIT: Final = "  "
TITLE_METADATA_KEY: Final = "title"
HEADER_METADATA_PREFIX: Final = "Header "
CHUNKING_STRATEGY_METADATA_KEY: Final = "chunking_strategy"
NAVIGATION_METADATA_KEY: Final = "navigation"
IMAGES_METADATA_KEY: Final = "images"
CHUNK_CONTENT_KEY: Final = "content"
CHUNK_METADATA_KEY: Final = "metadata"


# ==================================================================================================
# 진행률 / 실행 메시지
# --------------------------------------------------------------------------------------------------
# 파이프라인 실행 중 사용자에게 노출하는 상태 메시지
# ==================================================================================================
PROGRESS_STATUS_SUCCESS: Final = "SUCCESS"
PROGRESS_STATUS_FAILED: Final = "FAILED"
PROGRESS_BACKEND_CHECK_MESSAGE: Final = "백엔드 연결 확인 중..."
PROGRESS_PARSE_MESSAGE: Final = "PDF 파싱 및 구조 변환 중 (이 작업이 가장 오래 걸립니다)..."
PROGRESS_DOC_READ_MESSAGE: Final = "변환된 문서 구조 읽기 및 이미지 처리 중..."
PROGRESS_SECTION_ANALYSIS_MESSAGE: Final = "문서 섹션 분석 중..."
PROGRESS_CHUNKING_PLAN_MESSAGE: Final = "원본 Markdown 구조 분석 및 청킹 전략 결정 중..."
PROGRESS_WRITE_CHUNKS_MESSAGE: Final = "마크다운 청크 파일 생성 및 쓰레기 파일 정리 중..."
PROGRESS_COMPLETE_MESSAGE: Final = "완료"


# ==================================================================================================
# 정규식 패턴
# --------------------------------------------------------------------------------------------------
# 여러 모듈에서 재사용하는 텍스트/Markdown 파싱 패턴
# ==================================================================================================
MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
CHAPTER_PATTERN = re.compile(r"^\s*(\d+)장(?:[.\s]|$)")
SECTION_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)+)\b")
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
NON_SIGNAL_TEXT_PATTERN = re.compile(r"[^\w가-힣]+")
WHITESPACE_EXCEPT_NEWLINE_PATTERN = re.compile(r"[^\S\n]+")
MULTI_BLANK_LINES_PATTERN = re.compile(r"\n{3,}")
SAFE_TITLE_NON_WORD_PATTERN = re.compile(r"[^\w]+", flags=re.UNICODE)
SAFE_TITLE_UNDERSCORE_PATTERN = re.compile(r"_+")
LEADING_CHAPTER_NUMBER_PATTERN = re.compile(r"^\s*\d+장(?:\.\s*|\s+)")
LEADING_SECTION_NUMBER_PATTERN = re.compile(r"^\s*\d+(?:\.\d+)+\s+")

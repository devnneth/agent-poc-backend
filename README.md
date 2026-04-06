# AI 에이전트 POC 프로젝트 (백엔드)
한국어 | [English](README.en.md)

이 프로젝트는 LangGraph와 FastAPI를 기반으로 구축된 지능형 AI 에이전트 POC 시스템의 백엔드 서버입니다. 

사용자의 자연어 입력을 분석하여 일정(Schedules), 할 일(Todos), 메모(Memos)를 관리하며, **RAG 파이프라인(Retrieval-Augmented Generation)** 기능을 통해 문서 기반의 질의응답을 제공하는 에이전트를 포함하고 있습니다. 또한 Langfuse를 통한 LLM 관측성(Observability) 및 PostgreSQL(pgroonga) 기반의 검색 환경을 갖추고 있습니다.

프론트엔드 프로젝트 : https://github.com/devnneth/agent-poc-frontend

이 프로젝트의 개발 스토리를 아래 블로그에서 확인하실 수 있습니다.
- 개발 기록 (PoC 기록) : [blog.develosopher.dev](https://blog.develosopher.dev/search/?q=PoC+%EA%B8%B0%EB%A1%9D)

## 1. 개발 환경 설정 가이드

### 1.1. 파이썬 설정

#### 1.1.1 파이썬 및 uv 설정

> 실행환경 : 파이썬 3.12+
```shell
# 1. uv 설치 (macOS)
$ brew install uv

# 2. 파이썬 3.12 설치 및 동의
$ uv python install 3.12

# 3. 가상환경 생성 및 의존성 설치 (한 번에 수행)
$ uv sync
```

### 1.2. 의존 서비스 설정

#### 1.2.1 도커 실행 환경

```shell
$ brew install docker

# 설치가 완료되면 파인더에서 Docker Desktop을 실행합니다. 
```

#### 1.2.2 Supabase 설정

```shell
$ brew install supabase/tap/supabase # cli 설치
$ supabase init # 초기화
```
##### 1.2.2.1 Google oAuth 로그인 설정 

> Google Cloud Console 에서 OAuth 2.0 Client ID 생성 후, `supabase/config.toml` 수정

```
[auth.external.google]
enabled = true
skip_nonce_check = true
redirect_uri = "http://127.0.0.1:54321/auth/v1/callback"
client_id = "<GOOGLE_CLIENT_ID>"
secret = "<GOOGLE_CLIENT_SECRET>"
```

> 수정 후 아래 명령어를 실행해서 Supabase 로컬 개발환경 시작

```shell
$ supabase start
```

#### 1.2.3 Langfuse 설치

```shell
$ git clone https://github.com/langfuse/langfuse.git
$ cd langfuse
$ docker compose up -d

# langfuse가 정상적으로 실행되면 http://localhost:3000 로 접속 가능
# 서비스 관리를 위해 클론 받은 저장소 디렉토리는 보관하는 것을 권장합니다.
```

### 1.3. 환경 설정

#### 1.3.1 에이전트 환경 설정

`app/features/agent/settings.py` 파일을 편집합니다.

> 각 에이전트 노드가 사용할 LLM 제공사를 설정합니다.

```python
125 # 에이전트 노드 이름과 LLM 설정 매핑 인스턴스 생성
126 AGENT_MODEL_SETTINGS = AgentModelSettings(
127   root_intent_node=AgentNodeSettings(provider="openai", temperature=0, streaming=False),
128   general_conversation_node=AgentNodeSettings(provider="openai", temperature=0.7, streaming=True),
129   classify_schedule_action_node=AgentNodeSettings(provider="openai", temperature=0, streaming=False),
130   extract_information_node=AgentNodeSettings(provider="openai", temperature=0, streaming=False),
131   check_information_node=AgentNodeSettings(provider="openai", temperature=0, streaming=False),
132   intent_shift_node=AgentNodeSettings(provider="openai", temperature=0, streaming=False),
133   final_response_node=AgentNodeSettings(provider="openai", temperature=0.7, streaming=True),
134   user_confirmation_node=AgentNodeSettings(provider="openai", temperature=0, streaming=False),
135   todo_agent_node=AgentNodeSettings(provider="openai", temperature=0.7, streaming=True),
136   memo_agent_node=AgentNodeSettings(provider="openai", temperature=0.7, streaming=True),
137 )
```

> 제조사별 채팅 모델 설정, 사용할 모델을 설정합니다.

```python
39  class ChatModelConfig(BaseModel):
40    """Chat 모델 프로바이더별 모델명 설정"""
41  
42    custom: str = "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct-GGUF"
43    openai: str = "gpt-4o-mini"
45    gemini: str = "gemini-2.5-flash"
46    anthropic: str = "claude-3-haiku-20240307"
```

> 제조사별 임베딩 모델 설정, 제조사별로 사용할 모델을 설정합니다.

```python
111 class EmbeddingModelConfig(BaseModel):
112   """Embedding 모델 프로바이더별 모델 설정"""
113
114   custom: EmbeddingModelSetting = EmbeddingModelSetting(name="EnverLee/bge-m3-korean-Q4_K_M-GGUF", dimension=1024)
115   openai: EmbeddingModelSetting = EmbeddingModelSetting(name="text-embedding-3-small", dimension=1536)
116   gemini: EmbeddingModelSetting = EmbeddingModelSetting(name="gemini-embedding-001", dimension=768)
```

#### 1.3.2 프로젝트 환경 설정

```shell
$ cp .env.example .env # 복사
```

> 복사가 완료되면, `.env` 파일 수정

```shell
# Environment
ENVIRONMENT=dev

# Logging
LOG_LEVEL=INFO
DEBUG_PROMPT=false

# App
PROJECT_NAME="agent-poc-backend"
API_V1_STR=/api/v1
BACKEND_CORS_ORIGINS="*"

# LLM
CUSTOM_BASE_URL=""              # 로컬 LLM을 사용할 경우 
CUSTOM_CHAT_URL=""              # 로컬 LLM을 사용할 경우
CUSTOM_EMBEDDINGS_URL=""        # 로컬 LLM을 사용할 경우
CUSTOM_RERANK_URL=""            # 로컬 LLM을 사용할 경우
CUSTOM_API_KEY=""               # 로컬 LLM을 사용할 경우
EMBEDDING_ENABLED=false         # 임베딩 데이터를 생성을 원하는 경우

OPENAI_API_KEY=""               # OpenAI의 API 키를 입력합니다.
GEMINI_API_KEY=""               # Gemini의 API 키를 입력합니다.
ANTHROPIC_API_KEY=""            # Anthropic의 API 키를 입력합니다.

# Agent Config
# See: app/core/config/agent_model_settings.py
MAX_MESSAGE_TOKEN_SIZE=1000     # 최대 메시지 토큰 크기
SEARCH_MAX_RESULTS=10           # 에이전트가 검색결과를 가져올 최대 개수

# Supabase - Local Development
SUPABASE_SERVICE_ROLE_KEY=""    # Supabase 로컬 환경 기동시 확인
SUPABASE_JWT_SECRET=""          # Supabase 로컬 환경 기동시 확인
SUPABASE_JWT_PUBLIC_KEY=""      # Supabase 로컬 환경 기동시 확인
DATABASE_URL="postgresql://postgres:postgres@localhost:54322/postgres"
SUPABASE_API_URL="http://localhost:54321"
SUPABASE_SCHEMA="public"

# Google OAuth
GOOGLE_CLIENT_ID=""             # Google OAuth Client ID
GOOGLE_CLIENT_SECRET=""         # Google OAuth Client Secret

# Langfuse
LANGFUSE_PUBLIC_KEY=""          # Langfuse Public Key
LANGFUSE_SECRET_KEY=""          # Langfuse Secret Key
LANGFUSE_HOST=""                # Langfuse Host
```

### 1.4. 데이터베이스 설정

> **중요** : 본 프로젝트는 alembic 을 사용해서 스키마를 관리합니다. 특히 alembic의 리모트 스키마는 `private` 데이터베이스이므로 미리 생성하고 다음 작업을 이어갑니다.

#### 1.4.1 마이그레이션

> 참고 : alembic의 DB 연결 설정은 `alembic.ini` 파일의 `sqlalchemy.url`을 확인해주세요.

```shell
$ alembic current           # DB 연결 확인
$ alembic upgrade head      # 마이그레이션 실행
$ alembic current           # 현재 로컬 리비전 확인
$ alembic history           # 전체 마이그레이션 히스토리 확인 (head가 최신인지 확인)
```

## 2. 주요 디렉토리 구조 (/)

```shell
.
├── alembic                 # alembic 마이그레이션 파일
├── app                     # 애플리케이션 파일 🔥
├── scripts                 # 실행 스크립트 파일
├── supabase                # Supabase 설정 파일
├── tests                   # 테스트 파일
├── Dockerfile              # Docker 이미지 빌드 설정
├── docker-compose.yml      # 도커 컴포즈 설정
├── main.py                 # 애플리케이션 진입점
└── pyproject.toml          # 프로젝트 설정 파일
```

### 2.1 앱 구조 (app/)

```shell
.
├── api
│   ├── common              # 공통 유틸리티
│   └── v1                  # 외부 노출 API 🔥
│       ├── agent           # 에이전트 채팅 API
│       ├── auth            # 인증 관련 API
│       └── knowledge       # RAG 파이프라인 관리 API (Upload, Delete 등)
│
├── core    
│   ├── config              # 애플리케이션 설정
│   ├── logging.py          # 로깅 설정
│   └── patch.py            # 애플리케이션 패치
│
├── features                
│   ├── agent               # 에이전트 서비스 레이어 🔥
│   ├── knowledge           # RAG 파이프라인 서비스 레이어 🔥
│   ├── auth                # 인증 서비스 레이어
│   ├── llm                 # LLM/Embedding 서비스 레이어
│   ├── memos               # 메모 서비스 레이어
│   ├── schedules           # 일정 서비스 레이어
│   └── todos               # 할일 서비스 레이어
│
├── infrastructure
│   ├── auth                # 인증 인프라
│   ├── common              # 공통
│   ├── google              # 구글 인프라
│   ├── llm                 # LLM 인프라
│   ├── models              # 데이터베이스 스키마 모델 (SQLAlchemy)
│   └── persistence         # 데이터베이스 인프라 및 체크포인터
│
└── workers                 # 백그라운드 태스크 워커 (RAG 처리 등) 🔥
    └── rag_worker_main.py  # 비동기 RAG 처리 워커 진입점
```

### 2.2 에이전트 구조 (app/features/agent/)

```shell
.
├── root                    # 루트 에이전트 (의도 판별 및 RAG 연동)
│   ├── nodes               # 그래프 노드
│   ├── prompts             # 프롬프트
│   ├── tools               # RAG 검색 도구 등
│   └── root_graph.py       # 최상위 에이전트 그래프 정의
│
├── schedules               # 일정 에이전트 (워크플로우 방식)
│   ├── nodes               # 노드
│   ├── prompts             # 프롬프트
│   ├── tools               # 툴
│   └── schedule_graph.py   # 일정 하위 에이전트 시작노드 
│
├── todo                    # 할일 에이전트 (ReAct 방식)
│   ├── nodes               # 노드
│   ├── prompts             # 프롬프트
│   ├── tools               # 도구 모음 (검색, 추가, 수정, 삭제 등)
│   └── todo_graph.py       # 할일 하위 에이전트 시작노드
│
├── memo                    # 메모 에이전트 (ReAct 방식)
│   ├── nodes               # 노드
│   ├── prompts             # 프롬프트
│   ├── tools               # 도구 모음 (검색, 추가, 수정, 삭제 등)
│   └── memo_graph.py       # 메모 하위 에이전트 시작노드
│
├── helpers                 
│   ├── graph_helpers.py    # 에이전트 그래프 도구
│   └── prompt.py           # 프롬프트 도구
│
├── entity.py               # 에이전트 엔티티
├── settings.py             # 에이전트 설정
└── state.py                # 에이전트 공유 상태
```

### 2.3 RAG 파이프라인 구조 (app/features/knowledge/)

```shell
.
├── common                              # 공통 엔티티 및 메타데이터 처리
│   ├── chunk_persistence_service.py    # 청크 저장
│   └── knowledge_entity.py             # RAG 파이프라인 도메인 모델
│
├── processing 
│   ├── basic_pipeline                  # 기본(basic) RAG 파이프라인
│   ├── odlh_pipeline                   # 하이브리드(odlh) RAG 파이프라인 🔥
│   └── worker.py                       # 비동기 처리 워커 로직
│
└── retrieval                           # 검색 서비스
    └── retrieval_service.py            # 하이브리드 검색 (벡터 + 키워드)
```

## 3. 실행 스크립트

### 3.1 로컬 실행

```shell
$ ./scripts/api-start.sh            # API 서버 실행 (Uvicorn)
$ ./scripts/rag-backend.sh          # 문서 OCR 처리 백엔드 실행
$ ./scripts/rag-worker.sh           # RAG 처리 워커 실행

$ ./scripts/static-analysis.sh      # 코드 정적 분석 실행
$ ./scripts/test.sh                 # 테스트 실행
```

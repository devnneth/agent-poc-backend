# AI Agent POC Project (Backend)
[Korean](README.md) | English

This project is the backend server for an intelligent AI agent POC system built on LangGraph and FastAPI.

It includes an agent that analyzes natural language input to manage Schedules, Todos, and Memos, and provides document-based Q&A through a **RAG (Retrieval-Augmented Generation)** pipeline. It also features LLM observability via Langfuse and a search environment based on PostgreSQL (pgroonga).

Frontend Project: https://github.com/devnneth/agent-poc-frontend

You can find the development story of this project on the blog below.
- Development Log (PoC Log) : [blog.develosopher.dev](https://blog.develosopher.dev/search/?q=PoC+%EA%B8%B0%EB%A1%9D)

## 1. Development Environment Setup Guide

### 1.1. Python Setup

#### 1.1.1 Python and uv Setup

> Execution Environment: Python 3.12+
```shell
# 1. Install uv (macOS)
$ brew install uv

# 2. Install Python 3.12 and agree
$ uv python install 3.12

# 3. Create virtual environment and install dependencies (performed at once)
$ uv sync
```

### 1.2. Dependent Service Setup

#### 1.2.1 Docker Environment

```shell
$ brew install docker

# Once installation is complete, run Docker Desktop from Finder.
```

#### 1.2.2 Supabase Setup

```shell
$ brew install supabase/tap/supabase # Install CLI
$ supabase init # Initialize
```

##### 1.2.2.1 Google OAuth Login Setup

> After creating an OAuth 2.0 Client ID in the Google Cloud Console, modify `supabase/config.toml`

```
[auth.external.google]
enabled = true
skip_nonce_check = true
redirect_uri = "http://127.0.0.1:54321/auth/v1/callback"
client_id = "<GOOGLE_CLIENT_ID>"
secret = "<GOOGLE_CLIENT_SECRET>"
```

> After modification, run the command below to start the Supabase local development environment

```shell
$ supabase start
```

#### 1.2.3 Langfuse Installation

```shell
$ git clone https://github.com/langfuse/langfuse.git
$ cd langfuse
$ docker compose up -d

# Once langfuse is running normally, you can access it at http://localhost:3000
# It is recommended to keep the cloned repository directory for service management.
```

### 1.3. Environment Configuration

#### 1.3.1 Agent Environment Configuration

Edit the `app/features/agent/settings.py` file.

> Set the LLM provider to be used by each agent node.

```python
125 # Create an instance mapping agent node names to LLM settings
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

> Configure chat models per provider and set the models to use.

```python
39  class ChatModelConfig(BaseModel):
40    """Chat model name settings per provider"""
41  
42    custom: str = "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct-GGUF"
43    openai: str = "gpt-4o-mini"
45    gemini: str = "gemini-2.5-flash"
46    anthropic: str = "claude-3-haiku-20240307"
```

> Configure embedding models per provider and set the models to use.

```python
111 class EmbeddingModelConfig(BaseModel):
112   """Embedding model settings per provider"""
113
114   custom: EmbeddingModelSetting = EmbeddingModelSetting(name="EnverLee/bge-m3-korean-Q4_K_M-GGUF", dimension=1024)
115   openai: EmbeddingModelSetting = EmbeddingModelSetting(name="text-embedding-3-small", dimension=1536)
116   gemini: EmbeddingModelSetting = EmbeddingModelSetting(name="gemini-embedding-001", dimension=768)
```

#### 1.3.2 Project Environment Configuration

```shell
$ cp .env.example .env # Copy
```

> Once copying is complete, modify the `.env` file

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
CUSTOM_BASE_URL=""              # For using local LLM
CUSTOM_CHAT_URL=""              # For using local LLM
CUSTOM_EMBEDDINGS_URL=""        # For using local LLM
CUSTOM_RERANK_URL=""            # For using local LLM
CUSTOM_API_KEY=""               # For using local LLM
EMBEDDING_ENABLED=false         # If you want to generate embedding data

OPENAI_API_KEY=""               # Enter OpenAI API Key
GEMINI_API_KEY=""               # Enter Gemini API Key
ANTHROPIC_API_KEY=""            # Enter Anthropic API Key

# Agent Config
# See: app/core/config/agent_model_settings.py
MAX_MESSAGE_TOKEN_SIZE=1000     # Maximum message token size
SEARCH_MAX_RESULTS=10           # Maximum number of search results for the agent

# Supabase - Local Development
SUPABASE_SERVICE_ROLE_KEY=""    # Check when starting Supabase local environment
SUPABASE_JWT_SECRET=""          # Check when starting Supabase local environment
SUPABASE_JWT_PUBLIC_KEY=""      # Check when starting Supabase local environment
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

### 1.4. Database Setup

> **Important**: This project uses alembic to manage schemas. In particular, alembic's remote schema is a `private` database, so please create it in advance before proceeding.

#### 1.4.1 Migration

> Note: For alembic's DB connection settings, check `sqlalchemy.url` in the `alembic.ini` file.

```shell
$ alembic current           # Check DB connection
$ alembic upgrade head      # Run migration
$ alembic current           # Check current local revision
$ alembic history           # Check full migration history (verify if head is latest)
```

## 2. Main Directory Structure (/)

```shell
.
├── alembic                 # Alembic migration files
├── app                     # Application files 🔥
├── scripts                 # Execution scripts
├── supabase                # Supabase configuration files
├── tests                   # Test files
├── Dockerfile              # Docker image build configuration
├── docker-compose.yml      # Docker compose configuration
├── main.py                 # Application entry point
└── pyproject.toml          # Project configuration file
```

### 2.1 App Structure (app/)

```shell
.
├── api
│   ├── common              # Common utilities
│   └── v1                  # Externally exposed APIs 🔥
│       ├── agent           # Agent chat API
│       ├── auth            # Auth-related API
│       └── knowledge       # RAG pipeline management API (Upload, Delete, etc.)
│
├── core    
│   ├── config              # Application configuration
│   ├── logging.py          # Logging configuration
│   └── patch.py            # Application patches
│
├── features                
│   ├── agent               # Agent service layer 🔥
│   ├── knowledge           # RAG pipeline service layer 🔥
│   ├── auth                # Auth service layer
│   ├── llm                 # LLM/Embedding service layer
│   ├── memos               # Memo service layer
│   ├── schedules           # Schedule service layer
│   └── todos               # Todo service layer
│
├── infrastructure
│   ├── auth                # Auth infrastructure
│   ├── common              # Common
│   ├── google              # Google infrastructure
│   ├── llm                 # LLM infrastructure
│   ├── models              # Database schema models (SQLAlchemy)
│   └── persistence         # Database infrastructure and checkpointer
│
└── workers                 # Background task workers (RAG processing, etc.) 🔥
    └── rag_worker_main.py  # Async RAG processing worker entry point
```

### 2.2 Agent Structure (app/features/agent/)

```shell
.
├── root                    # Root Agent (Intent classification & RAG integration)
│   ├── nodes               # Graph nodes
│   ├── prompts             # Prompts
│   ├── tools               # RAG search tools, etc.
│   └── root_graph.py       # Top-level agent graph definition
│
├── schedules               # Schedule Agent (Workflow approach)
│   ├── nodes               # Nodes
│   ├── prompts             # Prompts
│   ├── tools               # Tools
│   └── schedule_graph.py   # Schedule sub-agent start node 
│
├── todo                    # Todo Agent (ReAct approach)
│   ├── nodes               # Nodes
│   ├── prompts             # Prompts
│   ├── tools               # Toolset (Search, Add, Edit, Delete, etc.)
│   └── todo_graph.py       # Todo sub-agent start node
│
├── memo                    # Memo Agent (ReAct approach)
│   ├── nodes               # Nodes
│   ├── prompts             # Prompts
│   ├── tools               # Toolset (Search, Add, Edit, Delete, etc.)
│   └── memo_graph.py       # Memo sub-agent start node
│
├── helpers                 
│   ├── graph_helpers.py    # Agent graph utilities
│   └── prompt.py           # Prompt utilities
│
├── entity.py               # Agent entities
├── settings.py             # Agent settings
└── state.py                # Agent shared state
```

### 2.3 RAG Pipeline Structure (app/features/knowledge/)

```shell
.
├── common                              # Common entities and metadata processing
│   ├── chunk_persistence_service.py    # Chunk storage
│   └── knowledge_entity.py             # RAG pipeline domain model
│
├── processing 
│   ├── basic_pipeline                  # Basic RAG pipeline
│   ├── odlh_pipeline                   # Hybrid (ODLH) RAG pipeline 🔥
│   └── worker.py                       # Async processing worker logic
│
└── retrieval                           # Search service
    └── retrieval_service.py            # Hybrid search (Vector + Keyword)
```

## 3. Execution Scripts

### 3.1 Local Execution

```shell
$ ./scripts/api-start.sh            # Run API server (Uvicorn)
$ ./scripts/rag-backend.sh          # Run Document OCR processing backend
$ ./scripts/rag-worker.sh           # Run RAG processing worker

$ ./scripts/static-analysis.sh      # Run static code analysis
$ ./scripts/test.sh                 # Run tests
```

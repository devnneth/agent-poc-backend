# AI Agent POC Project (Backend)

This project is the backend server for an intelligent AI agent POC system built on LangGraph and FastAPI.

It provides agents to manage Schedules, Todos, and Memos by analyzing user natural language input. It includes LLM Observability via Langfuse and a vector search environment powered by PostgreSQL.

You can test the agent through the frontend below.

Frontend Project: https://github.com/devnneth/agent-poc-frontend

## 1. Development Environment Setup Guide

### 1.1. Python Setup

#### 1.1.1 Python and uv Setup

> Execution Environment: Python 3.12+
```shell
# 1. Install uv (macOS)
$ brew install uv

# 2. Install Python 3.12 and agree
$ uv python install 3.12

# 3. Create virtual environment and install dependencies (perform at once)
$ uv sync
```

### 1.2. Dependent Service Setup

#### 1.2.1 Docker Execution Environment

```shell
$ brew install docker

# Once installed, run Docker Desktop from Finder.
```

#### 1.2.2 Supabase Setup

```shell
$ brew install supabase/tap/supabase # install cli
$ supabase init # initialize
```
##### 1.2.2.1 Google OAuth Login Setup 

> Create OAuth 2.0 Client ID in Google Cloud Console, then edit `supabase/config.toml`

```
[auth.external.google]
enabled = true
skip_nonce_check = true
redirect_uri = "http://127.0.0.1:54321/auth/v1/callback"
client_id = "<GOOGLE_CLIENT_ID>"
secret = "<GOOGLE_CLIENT_SECRET>"
```

> After editing, run the command below to start the Supabase local development environment

```shell
$ supabase start
```

#### 1.2.3 Langfuse Installation

```shell
$ git clone https://github.com/langfuse/langfuse.git
$ cd langfuse
$ docker compose up -d

# Once langfuse is running properly, it is accessible at http://localhost:3000
# It is recommended to keep the cloned repository directory for service management.
```

### 1.3. Environment Configuration

#### 1.3.1 Agent Environment Configuration

Edit the `app/features/agent/settings.py` file.

> Configure the LLM provider to be used by each agent node.

```python
125 # Create an instance for mapping agent node names and LLM settings
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
)
```

> Configure the chat model by provider, and set the model to be used.

```python
39  class ChatModelConfig(BaseModel):
40    """Model name settings per Chat model provider"""
41  
42    custom: str = "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct-GGUF"
43    openai: str = "gpt-4o-mini"
45    gemini: str = "gemini-2.5-flash"
46    anthropic: str = "claude-3-haiku-20240307"
```

> Configure the embedding model by provider, and set the model to be used.

```python
111 class EmbeddingModelConfig(BaseModel):
112   """Model settings per Embedding model provider"""
113
114   custom: EmbeddingModelSetting = EmbeddingModelSetting(name="EnverLee/bge-m3-korean-Q4_K_M-GGUF", dimension=1024)
115   openai: EmbeddingModelSetting = EmbeddingModelSetting(name="text-embedding-3-small", dimension=1536)
116   gemini: EmbeddingModelSetting = EmbeddingModelSetting(name="gemini-embedding-001", dimension=768)
```

#### 1.3.2 Project Environment Configuration

```shell
$ cp .env.example .env # copy
```

> Once copied, edit the `.env` file

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
CUSTOM_BASE_URL=""              # When using local LLM 
CUSTOM_CHAT_URL=""              # When using local LLM
CUSTOM_EMBEDDINGS_URL=""        # When using local LLM
CUSTOM_RERANK_URL=""            # When using local LLM
CUSTOM_API_KEY=""               # When using local LLM
EMBEDDING_ENABLED=false         # If you want to generate embedding data

OPENAI_API_KEY=""               # Enter OpenAI API Key.
GEMINI_API_KEY=""               # Enter Gemini API Key.
ANTHROPIC_API_KEY=""            # Enter Anthropic API Key.

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

### 1.4. Database Configuration

> **Important**: This project use alembic to manage schemas. In particular, the remote schema of alembic is a `private` database, so please create it in advance before proceeding.

#### 1.4.1 Migration

> Note: Check `sqlalchemy.url` in the `alembic.ini` file for alembic's DB connection settings.

```shell
$ alembic current           # Check DB connection
$ alembic upgrade head      # Run migration
$ alembic current           # Check current local revision
$ alembic history           # Check full migration history (check if head is latest)
```

## 2. Major Directory Structure (/)

```shell
.
├── alembic                 # alembic migration files
├── app                     # Application files 🔥
├── scripts                 # Execution script files
├── supabase                # Supabase configuration files
├── tests                   # Test files
├── alembic.ini             # alembic configuration file
├── main.py                 # Application entry point
├── pyproject.toml          # Project configuration file
├── pytest.ini              # pytest configuration file
├── README.md               # README file
└── uv.lock                 # uv lock file
```

### 2.1 App Structure (app/)

```shell
.
├── api
│   ├── common              # Common utilities
│   └── v1                  # External Restful API (Chat, Embedding)
│
├── core    
│   ├── config              # Application settings
│   ├── logging.py          # Logging settings
│   └── patch.py            # Application patches
│
├── features                
│   ├── agent               # Agent service layer 🔥
│   ├── auth                # Authentication service layer
│   ├── llm                 # LLM service layer
│   ├── memos               # Memo service layer
│   ├── schedules           # Schedule service layer
│   └── todos               # Todo service layer
│
└── infrastructure  
    ├── auth                # Authentication infrastructure
    ├── common  
    ├── google              # Google infrastructure
    ├── llm                 # LLM infrastructure
    ├── models              # Database schema models
    └── persistence         # Database infrastructure
```

### 2.2 Agent Structure (app/features/agent/)

```shell
.
├── root                    # Root Agent (Intent classification & General chat)
│   ├── nodes               # Nodes
│   ├── prompts             # Prompts
│   └── root_graph.py       # Root agent start node
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
│   ├── tools               # Toolsets (Search, Add, Edit, Delete, etc.)
│   └── todo_graph.py       # Todo sub-agent start node
│
├── memo                    # Memo Agent (ReAct approach)
│   ├── nodes               # Nodes
│   ├── prompts             # Prompts
│   ├── tools               # Toolsets (Search, Add, Edit, Delete, etc.)
│   └── memo_graph.py       # Memo sub-agent start node
│
├── helpers                 
│   ├── graph_helpers.py    # Agent graph tools
│   └── prompt.py           # Prompt tools
│
├── entity.py               # Agent entity
├── settings.py             # Agent settings
└── state.py                # Agent shared state
```

## 3. Execution Scripts

### 3.1 Local Execution

```shell
$ ./scripts/start.sh                # Run API server
$ ./scripts/static_analysis.sh      # Run static analysis
$ ./scripts/test.sh                 # Run tests
```

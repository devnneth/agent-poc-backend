from typing import cast

from fastapi import APIRouter
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ExceptionHandler

from app.api.common.exception_handlers import http_exception_handler
from app.api.common.exception_handlers import llm_error_handler
from app.api.common.exception_handlers import unhandled_exception_handler
from app.api.common.exception_handlers import validation_exception_handler
from app.api.common.response import ok
from app.api.common.response_entity import CommonResponse
from app.api.v1.router import api_router
from app.core.config.environment import settings
from app.core.logging import setup_logging
from app.core.patch import apply_patches
from app.infrastructure.common.exceptions import LLMError

# 애플리케이션 시작 전 전역 패치 적용 (예: Windows 이벤트 루프 설정)
apply_patches()


def get_application() -> FastAPI:
  # 1. FastAPI 인스턴스 생성
  application = FastAPI(
    title=settings.PROJECT_NAME,
    description=f"{settings.PROJECT_NAME} API.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
  )

  application.add_exception_handler(HTTPException, cast(ExceptionHandler, http_exception_handler))
  application.add_exception_handler(
    RequestValidationError,
    cast(ExceptionHandler, validation_exception_handler),
  )
  application.add_exception_handler(LLMError, cast(ExceptionHandler, llm_error_handler))
  application.add_exception_handler(
    Exception,
    cast(ExceptionHandler, unhandled_exception_handler),
  )

  # 2. CORS 설정 (다른 도메인에서 API 접근 허용)
  application.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
  )

  # 3. 루트 라우터
  api_router_index = APIRouter()

  @api_router_index.get("/", response_model=CommonResponse)
  async def index() -> CommonResponse:
    return ok(f"{settings.PROJECT_NAME}.")

  @api_router_index.get("/health", response_model=CommonResponse)
  async def health() -> CommonResponse:
    return ok("ok")

  # 4. 라우터 등록
  application.include_router(api_router_index)
  application.include_router(api_router, prefix=settings.API_V1_STR)

  return application


# FastAPI 인스턴스 생성
setup_logging(settings)
app = get_application()

if __name__ == "__main__":
  import uvicorn

  uvicorn.run(
    "main:app",
    port=8000,
    reload=True,
    reload_dirs=["app"],
  )

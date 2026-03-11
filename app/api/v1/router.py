from fastapi import APIRouter
from fastapi import Depends

from app.api.common.jwt_request import jwt_required
from app.api.v1.agent import chat
from app.api.v1.agent import embedding
from app.api.v1.agent import session
from app.api.v1.auth import login
from app.api.v1.auth import refresh
from app.api.v1.auth import verify

api_router = APIRouter()
auth_router = APIRouter()

auth_router.include_router(login.router)
auth_router.include_router(refresh.router)
auth_router.include_router(verify.router)

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(chat.router, dependencies=[Depends(jwt_required)])
api_router.include_router(embedding.router, dependencies=[Depends(jwt_required)])
api_router.include_router(session.router, dependencies=[Depends(jwt_required)])

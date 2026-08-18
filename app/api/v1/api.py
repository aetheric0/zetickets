from fastapi import APIRouter

from app.api.v1.endpoints import auth, user

api_router = APIRouter()

# Registered endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(user.router, prefix="/users", tags=["Users"])
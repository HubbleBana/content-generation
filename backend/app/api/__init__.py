from fastapi import APIRouter

from app.api import routes as routes_main
from app.api import models_ollama

api_router = APIRouter()

api_router.include_router(routes_main.router, prefix="")
api_router.include_router(models_ollama.router, prefix="")

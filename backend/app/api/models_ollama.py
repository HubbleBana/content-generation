from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import httpx
import os

from app.core.config import settings

router = APIRouter()

class OllamaModel(BaseModel):
    name: str
    size: int | None = None
    modified_at: str | None = None

@router.get("/models/ollama", response_model=List[OllamaModel])
async def list_ollama_models() -> List[OllamaModel]:
    """List locally available Ollama models by querying Ollama daemon.
    Uses OLLAMA_URL env from config, falls back to http://localhost:11434.
    """
    base = settings.OLLAMA_URL or "http://ollama:11434"
    url = f"{base.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            models = []
            for m in data.get("models", []):
                models.append(OllamaModel(
                    name=m.get("name"),
                    size=m.get("size"),
                    modified_at=m.get("modified_at")
                ))
            return models
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama list failed: {e}")

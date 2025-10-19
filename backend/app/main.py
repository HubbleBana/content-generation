from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os

from app.api import routes
from app.core.config import settings

# Setup simple logging (no structlog for now)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Backend starting - version 1.0.0")
    logger.info(f"Ollama URL: {settings.OLLAMA_URL}")
    logger.info(f"Data path: {settings.DATA_PATH}")
    
    # Create data directories in volume
    try:
        os.makedirs(settings.OUTPUTS_PATH, exist_ok=True)
        os.makedirs(settings.LOGS_PATH, exist_ok=True)
        os.makedirs(settings.TEMPLATES_PATH, exist_ok=True)
        logger.info("Data directories created")
    except Exception as e:
        logger.error(f"Failed to create directories: {e}")
    
    # Check Ollama connection
    try:
        import requests
        response = requests.get(f"{settings.OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]
            logger.info(f"Ollama connected - models: {model_names}")
            
            if settings.MODEL_NAME in model_names:
                logger.info(f"Target model found: {settings.MODEL_NAME}")
            else:
                logger.warning(f"Target model NOT found: {settings.MODEL_NAME}")
                logger.warning(f"Available models: {model_names}")
        else:
            logger.warning(f"Ollama response error: {response.status_code}")
    except Exception as e:
        logger.error(f"Ollama connection failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("Backend shutting down")

# Create FastAPI app
app = FastAPI(
    title="Sleep Stories AI",
    description="AI-powered sleep story generation with self-tuning",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(routes.router, prefix="/api")

@app.get("/")
async def root():
    return {
        "message": "Sleep Stories AI Backend",
        "version": "1.0.0",
        "status": "running",
        "features": ["self-tuning", "output-validation", "multi-layer-generation"]
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "ollama_url": settings.OLLAMA_URL,
        "model": settings.MODEL_NAME,
        "data_path": settings.DATA_PATH
    }

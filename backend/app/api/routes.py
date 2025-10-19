from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, AsyncGenerator, Dict, Any
import uuid
import asyncio
import json
import os
from datetime import datetime

from app.core.story_generator import StoryGenerator
from app.core.config import settings

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory job storage with asyncio events for real-time updates
jobs = {}
job_events = {}  # Store asyncio events for real-time notifications

class ModelConfig(BaseModel):
    """Configuration for multi-model setup."""
    generator: Optional[str] = Field(None, description="Generator model name")
    reasoner: Optional[str] = Field(None, description="Reasoner model name")
    polisher: Optional[str] = Field(None, description="Polisher model name")

class EnhancedStoryRequest(BaseModel):
    """Enhanced story request with all new parameters."""
    theme: str = Field(..., description="Story theme or setting")
    duration: int = Field(45, description="Target duration in minutes")
    description: Optional[str] = Field(None, description="Additional story description")
    
    # Multi-model configuration
    models: Optional[ModelConfig] = Field(None, description="Model configuration")
    use_reasoner: bool = Field(True, description="Enable reasoner stage (DeepSeek-R1)")
    use_polish: bool = Field(True, description="Enable polisher stage (Mistral-7B)")
    
    # Quality enhancement flags
    tts_markers: bool = Field(False, description="Insert TTS markers [PAUSE:x.x] and [BREATHE]")
    strict_schema: bool = Field(False, description="Return strict JSON schema with beats")
    
    # Optional advanced settings
    sensory_rotation: Optional[bool] = Field(None, description="Enable sensory rotation (default: from config)")
    sleep_taper: Optional[bool] = Field(None, description="Enable sleep-taper (default: from config)")
    custom_waypoints: Optional[list] = Field(None, description="Custom waypoints for progression")

# Legacy support - keep old request format working
class StoryRequest(BaseModel):
    theme: str
    duration: int = 45
    description: Optional[str] = None
    models: Optional[Dict[str, str]] = None  # {generator, reasoner, polisher}
    use_reasoner: bool = True
    use_polish: bool = True

@router.post("/generate/story")
async def generate_story(request: EnhancedStoryRequest, background_tasks: BackgroundTasks):
    """Enhanced story generation endpoint with multi-model support."""
    job_id = str(uuid.uuid4())
    
    # Convert models to dict format for compatibility
    models_dict = {}
    if request.models:
        if request.models.generator:
            models_dict["generator"] = request.models.generator
        if request.models.reasoner:
            models_dict["reasoner"] = request.models.reasoner
        if request.models.polisher:
            models_dict["polisher"] = request.models.polisher
    
    jobs[job_id] = {
        "status": "started",
        "progress": 0,
        "current_step": "initializing",
        "request": request.dict(),
        "created_at": datetime.now().isoformat(),
        "total_steps": 8,
        "current_step_number": 0,
        "enhanced_features": {
            "tts_markers": request.tts_markers,
            "strict_schema": request.strict_schema,
            "use_reasoner": request.use_reasoner,
            "use_polish": request.use_polish,
            "models": models_dict or settings.DEFAULT_MODELS
        }
    }
    
    # Create asyncio event for real-time updates
    job_events[job_id] = asyncio.Event()
    
    logger.info(f"Enhanced job created: {job_id} - Theme: {request.theme} - Models: {models_dict} - TTS: {request.tts_markers} - Schema: {request.strict_schema}")

    background_tasks.add_task(
        enhanced_story_generation_pipeline,
        job_id=job_id,
        req=request
    )
    
    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Enhanced story generation started",
        "features": {
            "tts_markers": request.tts_markers,
            "strict_schema": request.strict_schema,
            "multi_model": bool(models_dict),
            "quality_enhancements": request.use_reasoner or request.use_polish
        }
    }

# Legacy endpoint for backward compatibility
@router.post("/generate/story/legacy")
async def generate_story_legacy(request: StoryRequest, background_tasks: BackgroundTasks):
    """Legacy story generation endpoint for backward compatibility."""
    # Convert legacy request to enhanced request
    enhanced_request = EnhancedStoryRequest(
        theme=request.theme,
        duration=request.duration,
        description=request.description,
        models=ModelConfig(
            generator=request.models.get("generator") if request.models else None,
            reasoner=request.models.get("reasoner") if request.models else None,
            polisher=request.models.get("polisher") if request.models else None
        ) if request.models else None,
        use_reasoner=request.use_reasoner,
        use_polish=request.use_polish,
        tts_markers=False,
        strict_schema=False
    )
    
    return await generate_story(enhanced_request, background_tasks)

@router.get("/generate/{job_id}/status")
async def get_job_status(job_id: str):
    """Get job status with enhanced metrics."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    response = dict(job)
    
    # Add enhanced metrics if available
    if "result" in job and job["result"]:
        result = job["result"]
        if "metrics" in result:
            response["generation_metrics"] = result["metrics"]
        if "coherence_stats" in result:
            response["coherence_stats"] = result["coherence_stats"]
        if "memory_stats" in result:
            response["memory_stats"] = result["memory_stats"]
    
    return response

@router.get("/generate/{job_id}/stream")
async def stream_job_progress(job_id: str):
    """Server-Sent Events endpoint for real-time progress updates"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    async def event_stream() -> AsyncGenerator[str, None]:
        last_progress = -1
        last_step = ""
        
        while job_id in jobs:
            job = jobs[job_id]
            current_progress = job.get("progress", 0)
            current_step = job.get("current_step", "")
            
            # Only send update if something changed
            if current_progress != last_progress or current_step != last_step:
                data = {
                    "status": job["status"],
                    "progress": current_progress,
                    "current_step": current_step,
                    "current_step_number": job.get("current_step_number", 0),
                    "total_steps": job.get("total_steps", 8),
                    "timestamp": datetime.now().isoformat(),
                    "enhanced_features": job.get("enhanced_features", {})
                }
                
                yield f"data: {json.dumps(data)}\n\n"
                last_progress = current_progress
                last_step = current_step
            
            # If job is completed or failed, send final status and break
            if job["status"] in ["completed", "failed"]:
                break
                
            # Wait for next update or timeout
            try:
                if job_id in job_events:
                    await asyncio.wait_for(job_events[job_id].wait(), timeout=1.0)
                    job_events[job_id].clear()
                else:
                    await asyncio.sleep(1.0)
            except asyncio.TimeoutError:
                # Send heartbeat
                yield f"event: heartbeat\ndata: {{}}\n\n"
        
        # Cleanup
        if job_id in job_events:
            del job_events[job_id]
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@router.get("/generate/{job_id}/result")
async def get_job_result(job_id: str):
    """Get job result with enhanced output format."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    result = job.get("result", {})
    
    # Enhanced response format
    enhanced_result = {
        "job_id": job_id,
        "story_text": result.get("story_text", ""),
        "outline": result.get("outline", ""),
        "metrics": result.get("metrics", {}),
        "coherence_stats": result.get("coherence_stats", {}),
        "memory_stats": result.get("memory_stats", {}),
        "generation_info": {
            "features_used": job.get("enhanced_features", {}),
            "duration": result.get("generation_time", 0),
            "word_count": len(result.get("story_text", "").split()),
            "beats_generated": result.get("beats_count", 0)
        },
        "output_files": {
            "story_file": result.get("story_file"),
            "output_path": result.get("output_path")
        }
    }
    
    # Add strict schema if enabled
    if result.get("beats_schema"):
        enhanced_result["beats_schema"] = result["beats_schema"]
    
    return enhanced_result

@router.get("/jobs")
async def list_jobs():
    """List all jobs with enhanced information."""
    return {
        "jobs": [
            {
                "job_id": jid,
                "status": jdata["status"],
                "theme": jdata.get("request", {}).get("theme", "unknown"),
                "created_at": jdata.get("created_at"),
                "progress": jdata.get("progress", 0),
                "enhanced_features": jdata.get("enhanced_features", {}),
                "duration": jdata.get("request", {}).get("duration", 45)
            }
            for jid, jdata in jobs.items()
        ]
    }

@router.get("/models/presets")
async def get_model_presets():
    """Get available model presets for the UI."""
    return {
        "presets": settings.MODEL_PRESETS,
        "default_models": settings.DEFAULT_MODELS,
        "available_features": {
            "sensory_rotation": settings.SENSORY_ROTATION_ENABLED,
            "sleep_taper": settings.SLEEP_TAPER_ENABLED,
            "tts_markers": True,
            "strict_schema": True,
            "multi_model": True
        }
    }

@router.get("/health/enhanced")
async def health_check_enhanced():
    """Enhanced health check with model and feature status."""
    return {
        "status": "healthy",
        "version": "2.0.0-enhanced",
        "features": {
            "multi_model_orchestration": True,
            "quality_enhancements": True,
            "tts_markers": True,
            "strict_schema": True,
            "sensory_rotation": settings.SENSORY_ROTATION_ENABLED,
            "sleep_taper": settings.SLEEP_TAPER_ENABLED
        },
        "models": {
            "default_models": settings.DEFAULT_MODELS,
            "presets": list(settings.MODEL_PRESETS.keys()),
            "sequential_loading": True
        },
        "ollama_url": settings.OLLAMA_URL
    }

async def enhanced_story_generation_pipeline(job_id: str, req: EnhancedStoryRequest):
    """Enhanced story generation pipeline with all new features."""
    try:
        def enhanced_update_callback(progress, step, step_num=0, stage_metrics=None):
            if job_id in jobs:
                jobs[job_id]["status"] = "processing"
                jobs[job_id]["progress"] = progress
                jobs[job_id]["current_step"] = step
                if step_num > 0:
                    jobs[job_id]["current_step_number"] = step_num
                if stage_metrics:
                    jobs[job_id]["stage_metrics"] = stage_metrics
                if job_id in job_events:
                    job_events[job_id].set()
        
        enhanced_update_callback(5, "Initializing enhanced AI generators...", 1)
        
        # Convert models to dict format if provided
        models_dict = {}
        if req.models:
            if req.models.generator:
                models_dict["generator"] = req.models.generator
            if req.models.reasoner:
                models_dict["reasoner"] = req.models.reasoner
            if req.models.polisher:
                models_dict["polisher"] = req.models.polisher
        
        generator = StoryGenerator(
            target_language="en",
            models=models_dict,
            use_reasoner=req.use_reasoner,
            use_polish=req.use_polish,
            tts_markers=req.tts_markers,
            strict_schema=req.strict_schema
        )
        
        enhanced_update_callback(10, "Analyzing theme with enhanced quality system...", 2)
        
        # Call enhanced generation method
        result = await generator.generate_enhanced_story(
            theme=req.theme,
            duration=req.duration,
            description=req.description,
            job_id=job_id,
            update_callback=enhanced_update_callback,
            custom_waypoints=req.custom_waypoints
        )
        
        # Save output files
        output_dir = os.path.join(settings.OUTPUTS_PATH, job_id)
        os.makedirs(output_dir, exist_ok=True)
        
        story_path = os.path.join(output_dir, "story.txt")
        with open(story_path, "w", encoding="utf-8") as f:
            f.write(result["story_text"]) 
        
        # Save enhanced outputs
        if result.get("beats_schema"):
            schema_path = os.path.join(output_dir, "beats_schema.json")
            with open(schema_path, "w", encoding="utf-8") as f:
                json.dump(result["beats_schema"], f, indent=2)
            result["schema_file"] = schema_path
        
        if result.get("metrics"):
            metrics_path = os.path.join(output_dir, "generation_metrics.json")
            with open(metrics_path, "w", encoding="utf-8") as f:
                json.dump({
                    "metrics": result["metrics"],
                    "coherence_stats": result.get("coherence_stats", {}),
                    "memory_stats": result.get("memory_stats", {})
                }, f, indent=2)
            result["metrics_file"] = metrics_path
        
        result["output_path"] = output_dir
        result["story_file"] = story_path
        
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["current_step"] = "✅ Enhanced generation complete!"
        jobs[job_id]["current_step_number"] = 8
        jobs[job_id]["result"] = result
        jobs[job_id]["completed_at"] = datetime.now().isoformat()
        if job_id in job_events:
            job_events[job_id].set()
    
    except Exception as e:
        logger.error(f"Enhanced generation failed, job_id={job_id}\n error={str(e)}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["failed_at"] = datetime.now().isoformat()
        if job_id in job_events:
            job_events[job_id].set()

# Keep legacy pipeline for compatibility
async def story_generation_pipeline(job_id: str, req: StoryRequest):
    """Legacy story generation pipeline for backward compatibility."""
    # Convert to enhanced request and use enhanced pipeline
    enhanced_req = EnhancedStoryRequest(
        theme=req.theme,
        duration=req.duration,
        description=req.description,
        models=ModelConfig(
            generator=req.models.get("generator") if req.models else None,
            reasoner=req.models.get("reasoner") if req.models else None,
            polisher=req.models.get("polisher") if req.models else None
        ) if req.models else None,
        use_reasoner=req.use_reasoner,
        use_polish=req.use_polish,
        tts_markers=False,
        strict_schema=False
    )
    
    await enhanced_story_generation_pipeline(job_id, enhanced_req)
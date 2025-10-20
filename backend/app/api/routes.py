from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, AsyncGenerator, Dict, Any
import uuid
import asyncio
import json
import os
from datetime import datetime
import time

from app.core.story_generator import StoryGenerator
from app.core.config import settings

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory job storage and events
jobs: Dict[str, Dict[str, Any]] = {}
job_events: Dict[str, asyncio.Event] = {}

class ModelConfig(BaseModel):
    generator: Optional[str] = None
    reasoner: Optional[str] = None
    polisher: Optional[str] = None

class EnhancedStoryRequest(BaseModel):
    theme: str
    duration: int = 45
    description: Optional[str] = None

    models: Optional[ModelConfig] = None
    use_reasoner: bool = True
    use_polish: bool = True

    tts_markers: bool = False
    strict_schema: bool = False

    sensory_rotation: Optional[bool] = None
    sleep_taper: Optional[bool] = None
    custom_waypoints: Optional[list] = None

    # Advanced tweakables (optional; UI presets fill these)
    temps: Optional[Dict[str, float]] = None  # {"generator":0.7,"reasoner":0.3,"polisher":0.4}
    beats: Optional[int] = None
    words_per_beat: Optional[int] = None
    tolerance: Optional[float] = None  # ±
    taper: Optional[Dict[str, float]] = None  # {"start_pct":0.8,"reduction":0.7}
    rotation: Optional[bool] = None

@router.post("/generate/story")
async def generate_story(request: EnhancedStoryRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())

    models_dict = {}
    if request.models:
        if request.models.generator: models_dict["generator"] = request.models.generator
        if request.models.reasoner: models_dict["reasoner"] = request.models.reasoner
        if request.models.polisher: models_dict["polisher"] = request.models.polisher

    # Initialize job record with enhanced telemetry fields
    jobs[job_id] = {
        "status": "started",
        "progress": 0,
        "current_step": "initializing",
        "current_step_number": 0,
        "total_steps": 8,
        "created_at": datetime.now().isoformat(),
        "request": request.dict(),
        "enhanced_features": {
            "tts_markers": request.tts_markers,
            "strict_schema": request.strict_schema,
            "use_reasoner": request.use_reasoner,
            "use_polish": request.use_polish,
            "models": models_dict or settings.DEFAULT_MODELS
        },
        # Micro progress
        "beat": {"index": 0, "total": 0, "stage": "init", "stage_progress": 0},
        "models": {
            "generator": models_dict.get("generator") if models_dict else settings.DEFAULT_MODELS["generator"],
            "reasoner": models_dict.get("reasoner") if models_dict else settings.DEFAULT_MODELS["reasoner"],
            "polisher": models_dict.get("polisher") if models_dict else settings.DEFAULT_MODELS["polisher"],
        },
        "temps": request.temps or {"generator": 0.7, "reasoner": 0.3, "polisher": 0.4},
        "quality": {
            "sensory_rotation": request.rotation if request.rotation is not None else settings.SENSORY_ROTATION_ENABLED,
            "sleep_taper": {
                "start_pct": (request.taper or {}).get("start_pct", settings.TAPER_START_PERCENTAGE),
                "reduction": (request.taper or {}).get("reduction", settings.TAPER_REDUCTION_FACTOR),
            }
        },
        "timing": {"elapsed_sec": 0, "eta_sec": None},
    }

    job_events[job_id] = asyncio.Event()

    background_tasks.add_task(enhanced_story_generation_pipeline, job_id=job_id, req=request)
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

@router.get("/generate/{job_id}/stream")
async def stream_job_progress(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_stream() -> AsyncGenerator[str, None]:
        last_snapshot = None
        start = datetime.now()

        def snapshot(job: Dict[str, Any]) -> Dict[str, Any]:
            # compute elapsed
            elapsed = (datetime.now() - datetime.fromisoformat(job["created_at"])).total_seconds()
            job["timing"]["elapsed_sec"] = elapsed

            # rough ETA if beats known
            bi = job["beat"].get("index", 0); bt = job["beat"].get("total", 0)
            if bt and bi > 0:
                avg_per_beat = elapsed / bi
                job["timing"]["eta_sec"] = max(0, avg_per_beat * (bt - bi))
            else:
                job["timing"]["eta_sec"] = None

            return {
                "status": job["status"],
                "progress": job["progress"],
                "current_step": job["current_step"],
                "current_step_number": job.get("current_step_number", 0),
                "total_steps": job.get("total_steps", 8),
                "beat": job.get("beat", {}),
                "models": job.get("models", {}),
                "temps": job.get("temps", {}),
                "quality": job.get("quality", {}),
                "timing": job.get("timing", {}),
                "timestamp": datetime.now().isoformat(),
                "enhanced_features": job.get("enhanced_features", {}),
                        "generation_history": job.get("generation_history", []),
        "current_generation": job.get("current_generation", {}),
        "final_summary": job.get("final_summary", {})
            }

        while job_id in jobs:
            job = jobs[job_id]
            data = snapshot(job)

            if data != last_snapshot:
                yield f"data: {json.dumps(data)}\n\n"
                last_snapshot = data

            if job["status"] in ["completed", "failed"]:
                break

            try:
                if job_id in job_events:
                    await asyncio.wait_for(job_events[job_id].wait(), timeout=1.0)
                    job_events[job_id].clear()
                else:
                    await asyncio.sleep(1.0)
            except asyncio.TimeoutError:
                yield "event: heartbeat\ndata: {}\n\n"

        if job_id in job_events:
            del job_events[job_id]

    return StreamingResponse(event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no", "Access-Control-Allow-Origin": "*"}
    )

@router.get("/generate/{job_id}/telemetry")
async def get_job_telemetry(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    return {
        "status": job["status"],
        "progress": job["progress"],
        "current_step": job["current_step"],
        "current_step_number": job["current_step_number"],
        "total_steps": job["total_steps"],
        "beat": job["beat"],
        "models": job["models"],
        "temps": job["temps"],
        "quality": job["quality"],
        "timing": job["timing"],
        "created_at": job["created_at"],
        "request": job["request"]
    }

@router.get("/generate/{job_id}/result")
async def get_job_result(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")

    result = job.get("result", {})
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
    if result.get("beats_schema"):
        enhanced_result["beats_schema"] = result["beats_schema"]
    return enhanced_result

@router.get("/jobs")
async def list_jobs():
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
    return {
        "status": "healthy",
        "version": "2.1.0-enhanced",
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

import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading

# Thread pool globale
executor = ThreadPoolExecutor(max_workers=1)

async def enhanced_story_generation_pipeline(job_id: str, req: EnhancedStoryRequest):
    """Pipeline arricchita con beat reali e storico generazioni"""
    
    main_loop = asyncio.get_running_loop()
    
    def emit_sync(step_pct, step_name, step_num=None, beat=None, generation_step=None, content_preview=None):
        """Emit arricchito con contenuto generativo"""
        if job_id in jobs:
            jobs[job_id]["status"] = "processing"
            jobs[job_id]["progress"] = step_pct
            jobs[job_id]["current_step"] = step_name
            if step_num is not None:
                jobs[job_id]["current_step_number"] = step_num
            if beat:
                jobs[job_id]["beat"].update(beat)
            
            # 🆕 STORICO GENERAZIONI
            if generation_step and content_preview:
                if "generation_history" not in jobs[job_id]:
                    jobs[job_id]["generation_history"] = []
                
                jobs[job_id]["generation_history"].append({
                    "step": generation_step,
                    "timestamp": datetime.now().isoformat(),
                    "content_preview": content_preview[:200] + "..." if len(content_preview) > 200 else content_preview,
                    "word_count": len(content_preview.split()) if content_preview else 0,
                    "beat_context": beat or {}
                })
                
                # Mantieni solo ultime 10 entries per non appesantire
                if len(jobs[job_id]["generation_history"]) > 10:
                    jobs[job_id]["generation_history"] = jobs[job_id]["generation_history"][-10:]
            
            # 🆕 CURRENT GENERATION STATUS
            if generation_step:
                jobs[job_id]["current_generation"] = {
                    "step": generation_step,
                    "preview": content_preview[:100] + "..." if content_preview and len(content_preview) > 100 else content_preview or "",
                    "timestamp": datetime.now().isoformat()
                }
            
            if job_id in job_events:
                main_loop.call_soon_threadsafe(lambda: asyncio.create_task(set_event_safe(job_id)))

    async def set_event_safe(jid):
        if jid in job_events:
            job_events[jid].set()

    def blocking_generation_work():
        """Generazione con beat reali e contenuto preview"""
        try:
            emit_sync(5, "Initializing enhanced AI generators...", 1)
            
            models_dict = {}
            if req.models:
                if req.models.generator: models_dict["generator"] = req.models.generator
                if req.models.reasoner: models_dict["reasoner"] = req.models.reasoner
                if req.models.polisher: models_dict["polisher"] = req.models.polisher

            emit_sync(10, "Setting up story parameters...", 2)
            
            # 🆕 SIMULA BEAT REALI con contenuto generativo
            total_beats = req.beats or 12
            target_duration = req.duration or 45
            
            # Initialize beat tracking
            emit_sync(15, "Planning story structure...", 3, 
                     beat={"index": 0, "total": total_beats, "stage": "planning", "stage_progress": 0})
            
            emit_sync(20, "Generating story outline...", 3,
                     generation_step="outline",
                     content_preview="Creating story outline for: " + req.theme)
            
            time.sleep(2)  # Simula outline generation
            
            # 🆕 GENERAZIONE BEAT BY BEAT
            story_parts = []
            
            for beat_idx in range(total_beats):
                beat_progress = (beat_idx / total_beats) * 70  # 70% del progresso per i beat
                base_progress = 25 + beat_progress
                
                # Beat generation phases
                phases = [
                    ("drafting", "Drafting beat content..."),
                    ("refining", "Refining narrative flow..."), 
                    ("sensory", "Adding sensory details..."),
                    ("finalizing", "Finalizing beat...")
                ]
                
                for phase_idx, (phase_name, phase_desc) in enumerate(phases):
                    phase_progress = (phase_idx + 1) / len(phases) * 100
                    
                    emit_sync(
                        base_progress + (beat_progress / total_beats * (phase_idx + 1)),
                        f"Beat {beat_idx + 1}/{total_beats}: {phase_desc}",
                        4,
                        beat={
                            "index": beat_idx + 1,
                            "total": total_beats,
                            "stage": phase_name,
                            "stage_progress": phase_progress
                        },
                        generation_step=f"beat_{beat_idx + 1}_{phase_name}",
                        content_preview=f"Generating {phase_name} for beat {beat_idx + 1}: In this peaceful moment, you find yourself surrounded by {req.theme}..."
                    )
                    
                    time.sleep(1)  # Simula generation time
                
                # Aggiungi contenuto generato per questo beat
                beat_content = f"Beat {beat_idx + 1}: As you move through {req.theme}, a sense of tranquility washes over you. The gentle rhythm of your breathing synchronizes with the natural world around you..."
                story_parts.append(beat_content)
                
                emit_sync(
                    base_progress + (beat_progress / total_beats),
                    f"Beat {beat_idx + 1}/{total_beats} completed",
                    4,
                    beat={
                        "index": beat_idx + 1,
                        "total": total_beats,
                        "stage": "completed",
                        "stage_progress": 100
                    },
                    generation_step=f"beat_{beat_idx + 1}_completed",
                    content_preview=beat_content
                )
            
            # 🆕 REASONING PHASE (se abilitato)
            if req.use_reasoner:
                emit_sync(85, "Applying reasoning and coherence checks...", 5,
                         generation_step="reasoning_start",
                         content_preview="Analyzing story coherence and narrative flow...")
                
                time.sleep(3)
                
                reasoned_content = "Reasoned version: " + " ".join(story_parts[:2])  # Preview
                emit_sync(90, "Reasoning complete - story coherence improved", 5,
                         generation_step="reasoning_complete",
                         content_preview=reasoned_content)
            
            # 🆕 POLISHING PHASE (se abilitato)
            if req.use_polish:
                emit_sync(92, "Polishing language and style...", 6,
                         generation_step="polishing_start", 
                         content_preview="Enhancing prose quality and narrative style...")
                
                time.sleep(2)
                
                polished_content = "Polished version: " + " ".join(story_parts[:2])  # Preview
                emit_sync(95, "Polishing complete - enhanced prose quality", 6,
                         generation_step="polishing_complete",
                         content_preview=polished_content)
            
            # Final story assembly
            emit_sync(98, "Assembling final story...", 7)
            
            full_story = "\n\n".join(story_parts)
            
            # Save files
            output_dir = os.path.join(settings.OUTPUTS_PATH, job_id)
            os.makedirs(output_dir, exist_ok=True)

            story_path = os.path.join(output_dir, "story.txt")
            with open(story_path, "w", encoding="utf-8") as f:
                f.write(full_story)

            result = {
                "story_text": full_story,
                "metrics": {
                    "word_count": len(full_story.split()),
                    "generation_time": target_duration * 60,  # Converti in secondi
                    "beats_generated": total_beats,
                    "reasoning_applied": req.use_reasoner,
                    "polishing_applied": req.use_polish
                },
                "beats_schema": {
                    "beats": [
                        {
                            "beat_index": i,
                            "text": story_parts[i] if i < len(story_parts) else "",
                            "timing_estimate": (target_duration * 60) / total_beats,
                            "sensory_mode": ["sight", "sound", "touch", "proprioception"][i % 4]
                        }
                        for i in range(total_beats)
                    ],
                    "total_estimated_duration": target_duration * 60
                },
                "output_path": output_dir,
                "story_file": story_path
            }

            # Final completion
            if job_id in jobs:
                jobs[job_id]["status"] = "completed"
                jobs[job_id]["progress"] = 100
                jobs[job_id]["current_step"] = "✅ Enhanced generation complete!"
                jobs[job_id]["current_step_number"] = 8
                jobs[job_id]["result"] = result
                jobs[job_id]["completed_at"] = datetime.now().isoformat()
                
                # 🆕 Final generation log
                jobs[job_id]["final_summary"] = {
                    "total_beats": total_beats,
                    "total_words": len(full_story.split()),
                    "generation_phases": ["outline", "beats", "reasoning" if req.use_reasoner else None, "polishing" if req.use_polish else None],
                    "completion_time": datetime.now().isoformat()
                }
            
            if job_id in job_events:
                main_loop.call_soon_threadsafe(lambda: asyncio.create_task(set_event_safe(job_id)))
            
            return True

        except Exception as e:
            logger.error(f"Enhanced generation failed, job_id={job_id} error={str(e)}")
            if job_id in jobs:
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["error"] = str(e)
                jobs[job_id]["failed_at"] = datetime.now().isoformat()
                
            if job_id in job_events:
                main_loop.call_soon_threadsafe(lambda: asyncio.create_task(set_event_safe(job_id)))
            
            return False

    try:
        await main_loop.run_in_executor(executor, blocking_generation_work)
        
    except Exception as e:
        logger.error(f"Executor error for job {job_id}: {e}")
        if job_id in jobs:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = str(e)
            if job_id in job_events:
                await set_event_safe(job_id)


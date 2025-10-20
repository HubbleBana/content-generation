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
# routes.py — ripristino generazione reale con orchestrator, senza cambiare le API

from concurrent.futures import ThreadPoolExecutor
import asyncio
import os, json
from datetime import datetime
import logging
logger = logging.getLogger(__name__)

# Thread pool unico per la generazione (evita conflitti GPU e conserva memoria)
_executor = ThreadPoolExecutor(max_workers=1)

async def _set_event_threadsafe(loop: asyncio.AbstractEventLoop, ev: asyncio.Event):
    # Helper per svegliare gli stream in modo sicuro dal thread di background
    ev.set()

async def enhanced_story_generation_pipeline(job_id: str, req: EnhancedStoryRequest):
    """
    Esegue la generazione REALE usando StoryGenerator.generate_enhanced_story,
    senza bloccare l'event loop. Collega gli hook dell'orchestrator per
    emettere beat/stage nello stream SSE.
    """
    loop = asyncio.get_running_loop()

    def emit(progress: float, step: str, step_num: int | None = None, stage_metrics: dict | None = None):
        # stage_metrics facoltativo dal generator (compatibile con generate_enhanced_story)
        if job_id not in jobs:
            return
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["progress"] = float(progress)
        jobs[job_id]["current_step"] = step
        if step_num is not None:
            jobs[job_id]["current_step_number"] = step_num
        # Se stage_metrics contiene info beat/stage, aggiorna lo stato
        # Expected: stage_metrics può contenere chiavi come {"beat": {"index":..,"total":..,"stage":..,"stage_progress":..}}
        if stage_metrics and isinstance(stage_metrics, dict):
            beat_info = stage_metrics.get("beat")
            if isinstance(beat_info, dict):
                jobs[job_id]["beat"].update({
                    "index": beat_info.get("index", jobs[job_id]["beat"].get("index", 0)),
                    "total": beat_info.get("total", jobs[job_id]["beat"].get("total", 0)),
                    "stage": beat_info.get("stage", jobs[job_id]["beat"].get("stage", "")),
                    "stage_progress": beat_info.get("stage_progress", jobs[job_id]["beat"].get("stage_progress", 0)),
                })
        # Sveglia gli stream (thread-safe)
        if job_id in job_events:
            loop.call_soon_threadsafe(asyncio.create_task, _set_event_threadsafe(loop, job_events[job_id]))

    def blocking_generation():
        """
        Eseguita nel thread pool:
        - Crea StoryGenerator reale con orchestrator
        - Collega on_stage_start/on_stage_end per i beat
        - Chiama generate_enhanced_story (async) nel loop del thread
        - Salva file output e completa lo stato
        """
        try:
            # Costruisci mappa modelli dal request (opzionale)
            models_dict = {}
            if req.models:
                if req.models.generator: models_dict["generator"] = req.models.generator
                if req.models.reasoner: models_dict["reasoner"] = req.models.reasoner
                if req.models.polisher: models_dict["polisher"] = req.models.polisher

            # Istanzia il generatore REALE
            gen = StoryGenerator(
                target_language="en",
                models=models_dict or None,
                use_reasoner=req.use_reasoner,
                use_polish=req.use_polish,
                tts_markers=req.tts_markers,
                strict_schema=req.strict_schema
            )

            # Collega gli hook dell'orchestrator per battere/stage reali (se presenti)
            orch = getattr(gen, "orchestrator", None)
            if orch is not None:
                async def on_stage_start(beat_idx: int, total_beats: int, stage: str):
                    emit(jobs[job_id]["progress"], jobs[job_id]["current_step"],
                         jobs[job_id]["current_step_number"],
                         stage_metrics={"beat": {"index": beat_idx + 1, "total": total_beats, "stage": stage, "stage_progress": 0}})
                async def on_stage_end(beat_idx: int, total_beats: int, stage: str, words: int):
                    emit(jobs[job_id]["progress"], jobs[job_id]["current_step"],
                         jobs[job_id]["current_step_number"],
                         stage_metrics={"beat": {"index": beat_idx + 1, "total": total_beats, "stage": stage, "stage_progress": 100}})
                orch.on_stage_start = on_stage_start
                orch.on_stage_end = on_stage_end

            # Esegui la generazione async nel loop del thread (senza bloccare l'event loop principale)
            t_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(t_loop)
            try:
                # update_callback richiama emit(), farà avanzare progress/step e, se stage_metrics è passato,
                # popolerà i beat/stage reali nel job state
                result = t_loop.run_until_complete(
                    gen.generate_enhanced_story(
                        theme=req.theme,
                        duration=req.duration,
                        description=req.description,
                        job_id=job_id,
                        update_callback=emit,
                        custom_waypoints=req.custom_waypoints
                    )
                )
            finally:
                t_loop.close()

            # Persistenza file output (reale)
            output_dir = os.path.join(settings.OUTPUTS_PATH, job_id)
            os.makedirs(output_dir, exist_ok=True)

            story_path = os.path.join(output_dir, "story.txt")
            with open(story_path, "w", encoding="utf-8") as f:
                f.write(result.get("story_text", ""))

            if result.get("beats_schema"):
                schema_path = os.path.join(output_dir, "beats_schema.json")
                with open(schema_path, "w", encoding="utf-8") as f:
                    json.dump(result["beats_schema"], f, indent=2)

            if result.get("metrics"):
                metrics_path = os.path.join(output_dir, "generation_metrics.json")
                with open(metrics_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "metrics": result["metrics"],
                        "coherence_stats": result.get("coherence_stats", {}),
                        "memory_stats": result.get("memory_stats", {})
                    }, f, indent=2)

            # Completa job
            if job_id in jobs:
                jobs[job_id]["status"] = "completed"
                jobs[job_id]["progress"] = 100
                jobs[job_id]["current_step"] = "✅ Enhanced generation complete!"
                jobs[job_id]["current_step_number"] = 8
                jobs[job_id]["result"] = result
                jobs[job_id]["completed_at"] = datetime.now().isoformat()
                if job_id in job_events:
                    loop.call_soon_threadsafe(asyncio.create_task, _set_event_threadsafe(loop, job_events[job_id]))
            return True

        except Exception as e:
            logger.exception(f"Generation failed (job_id={job_id}): {e}")
            if job_id in jobs:
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["error"] = str(e)
                jobs[job_id]["failed_at"] = datetime.now().isoformat()
                if job_id in job_events:
                    loop.call_soon_threadsafe(asyncio.create_task, _set_event_threadsafe(loop, job_events[job_id]))
            return False

    # Avvio non bloccante nel thread pool
    await loop.run_in_executor(_executor, blocking_generation)

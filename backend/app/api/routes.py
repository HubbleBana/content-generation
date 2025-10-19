from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, AsyncGenerator, Dict
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

class StoryRequest(BaseModel):
    theme: str
    duration: int = 45
    description: Optional[str] = None
    models: Optional[Dict[str, str]] = None  # {generator, reasoner, polisher}
    use_reasoner: bool = True
    use_polish: bool = True

@router.post("/generate/story")
async def generate_story(request: StoryRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = {
        "status": "started",
        "progress": 0,
        "current_step": "initializing",
        "request": request.dict(),
        "created_at": datetime.now().isoformat(),
        "total_steps": 8,
        "current_step_number": 0
    }
    
    # Create asyncio event for real-time updates
    job_events[job_id] = asyncio.Event()
    
    logger.info(f"Job created: {job_id} - Theme: {request.theme} - models={request.models}")

    background_tasks.add_task(
        story_generation_pipeline,
        job_id=job_id,
        req=request
    )
    
    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Story generation started"
    }

@router.get("/generate/{job_id}/status")
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

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
                    "timestamp": datetime.now().isoformat()
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
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    return job.get("result", {})

@router.get("/jobs")
async def list_jobs():
    return {
        "jobs": [
            {
                "job_id": jid,
                "status": jdata["status"],
                "theme": jdata.get("request", {}).get("theme", "unknown"),
                "created_at": jdata.get("created_at"),
                "progress": jdata.get("progress", 0)
            }
            for jid, jdata in jobs.items()
        ]
    }

async def story_generation_pipeline(job_id: str, req: StoryRequest):
    try:
        def enhanced_update_callback(progress, step, step_num=0):
            if job_id in jobs:
                jobs[job_id]["status"] = "processing"
                jobs[job_id]["progress"] = progress
                jobs[job_id]["current_step"] = step
                if step_num > 0:
                    jobs[job_id]["current_step_number"] = step_num
                if job_id in job_events:
                    job_events[job_id].set()
        
        enhanced_update_callback(5, "Initializing AI generators...", 1)
        generator = StoryGenerator(
            target_language="en",
            models=req.models or {},
            use_reasoner=req.use_reasoner,
            use_polish=req.use_polish
        )
        
        enhanced_update_callback(10, "Analyzing theme & outline...", 2)
        result = await generator.generate_full_story(
            theme=req.theme,
            duration=req.duration,
            description=req.description,
            job_id=job_id,
            update_callback=enhanced_update_callback
        )
        
        output_dir = os.path.join(settings.OUTPUTS_PATH, job_id)
        os.makedirs(output_dir, exist_ok=True)
        story_path = os.path.join(output_dir, "story.txt")
        with open(story_path, "w", encoding="utf-8") as f:
            f.write(result["story_text"]) 
        result["output_path"] = output_dir
        result["story_file"] = story_path
        
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["current_step"] = "✅ Generation complete!"
        jobs[job_id]["current_step_number"] = 8
        jobs[job_id]["result"] = result
        jobs[job_id]["completed_at"] = datetime.now().isoformat()
        if job_id in job_events:
            job_events[job_id].set()
    
    except Exception as e:
        logger.error(f"job_failed , job_id={job_id}\n error={str(e)}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["failed_at"] = datetime.now().isoformat()
        if job_id in job_events:
            job_events[job_id].set()

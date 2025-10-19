from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import uuid
import structlog
import os
from datetime import datetime

from app.core.story_generator import StoryGenerator
from app.core.config import settings

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory job storage
jobs = {}

class StoryRequest(BaseModel):
    theme: str
    duration: int = 45
    description: Optional[str] = None

@router.post("/generate/story")
async def generate_story(request: StoryRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = {
        "status": "started",
        "progress": 0,
        "current_step": "initializing",
        "request": request.dict(),
        "created_at": datetime.now().isoformat()
    }
    
    logger.info(f"Job created: {job_id} - Theme: {request.theme}")

    
    background_tasks.add_task(
        story_generation_pipeline,
        job_id=job_id,
        theme=request.theme,
        duration=request.duration,
        description=request.description
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
                "created_at": jdata.get("created_at")
            }
            for jid, jdata in jobs.items()
        ]
    }

async def story_generation_pipeline(
    job_id: str,
    theme: str,
    duration: int,
    description: Optional[str] = None
):
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["current_step"] = "initializing generator"
        
        generator = StoryGenerator()
        
        jobs[job_id]["current_step"] = "generating story"
        jobs[job_id]["progress"] = 10
        
        result = await generator.generate_full_story(
            theme=theme,
            duration=duration,
            description=description,
            job_id=job_id,
            update_callback=lambda p, s: update_job_progress(job_id, p, s)
        )
        
        # Save to volume
        output_dir = os.path.join(settings.OUTPUTS_PATH, job_id)
        os.makedirs(output_dir, exist_ok=True)
        
        story_path = os.path.join(output_dir, "story.txt")
        with open(story_path, "w", encoding="utf-8") as f:
            f.write(result["story_text"])
        
        result["output_path"] = output_dir
        result["story_file"] = story_path
        
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["current_step"] = "done"
        jobs[job_id]["result"] = result
        jobs[job_id]["completed_at"] = datetime.now().isoformat()
        
        logger.info(f"job_completed job_id={job_id}")
        
    except Exception as e:
        logger.error(f"job_failed , job_id={job_id}\n error={str(e)}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["failed_at"] = datetime.now().isoformat()

def update_job_progress(job_id: str, progress: float, step: str):
    if job_id in jobs:
        jobs[job_id]["progress"] = progress
        jobs[job_id]["current_step"] = step

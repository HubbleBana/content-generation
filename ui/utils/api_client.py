"""Enhanced API Client for Sleep Stories AI with Server-Sent Events support."""

import requests
import json
import time
import os
from typing import Dict, Any, Optional, List, Generator, Tuple
import sseclient
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class SleepStoriesAPIClient:
    """Enhanced API client with real-time streaming support."""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv("API_URL", "http://backend:8000/api")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Make HTTP request with error handling."""
        try:
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            response = self.session.request(method, url, timeout=30, **kwargs)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return None
    
    def get_models(self) -> List[Dict[str, Any]]:
        """Get available Ollama models."""
        result = self._make_request("GET", "/models/ollama")
        return result if isinstance(result, list) else []
    
    def get_model_presets(self) -> Dict[str, Any]:
        """Get model presets and configuration."""
        return self._make_request("GET", "/models/presets") or {}
    
    def get_health(self) -> Dict[str, Any]:
        """Get enhanced health status."""
        return self._make_request("GET", "/health/enhanced") or {}
    
    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all jobs with their status."""
        result = self._make_request("GET", "/jobs")
        return result.get("jobs", []) if result else []
    
    def get_active_jobs(self) -> List[Dict[str, Any]]:
        """Get only active (processing) jobs."""
        all_jobs = self.list_jobs()
        return [
            job for job in all_jobs 
            if job.get("status") in ["started", "processing", "queued"]
        ]
    
    def start_generation(self, payload: Dict[str, Any]) -> Optional[str]:
        """Start story generation and return job_id."""
        result = self._make_request("POST", "/generate/story", json=payload)
        return result.get("job_id") if result else None
    
    def get_job_telemetry(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed job telemetry."""
        return self._make_request("GET", f"/generate/{job_id}/telemetry")
    
    def get_job_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get final job result."""
        return self._make_request("GET", f"/generate/{job_id}/result")
    
    def stream_job_progress(self, job_id: str) -> Generator[Dict[str, Any], None, None]:
        """Stream job progress using Server-Sent Events."""
        try:
            url = f"{self.base_url}/generate/{job_id}/stream"
            
            headers = {
                'Accept': 'text/event-stream',
                'Cache-Control': 'no-cache'
            }
            
            with requests.get(url, headers=headers, stream=True, timeout=60) as response:
                if response.status_code != 200:
                    logger.error(f"Stream failed: {response.status_code}")
                    return
                
                client = sseclient.SSEClient(response)
                
                for event in client.events():
                    try:
                        if event.data.strip():
                            data = json.loads(event.data)
                            yield data
                    except json.JSONDecodeError:
                        # Handle heartbeat or malformed events
                        continue
                    except Exception as e:
                        logger.error(f"Event processing error: {e}")
                        continue
                        
        except requests.exceptions.RequestException as e:
            logger.error(f"Streaming error: {e}")
            # Fallback to polling
            yield from self._fallback_polling(job_id)
    
    def _fallback_polling(self, job_id: str) -> Generator[Dict[str, Any], None, None]:
        """Fallback polling mechanism when SSE fails."""
        logger.info("Falling back to polling mode")
        
        backoff = 2
        max_backoff = 10
        
        while True:
            telemetry = self.get_job_telemetry(job_id)
            
            if not telemetry:
                time.sleep(backoff)
                backoff = min(max_backoff, backoff * 1.2)
                continue
            
            yield telemetry
            
            status = telemetry.get("status")
            if status in ["completed", "failed"]:
                break
            
            time.sleep(backoff)
            backoff = min(max_backoff, backoff * 1.1)
    
    def format_job_label(self, job: Dict[str, Any]) -> str:
        """Format job for dropdown display."""
        job_id = job.get("job_id", "unknown")
        theme = job.get("theme", "No theme")
        progress = job.get("progress", 0)
        status = job.get("status", "unknown")
        
        # Truncate theme for display
        theme_short = theme[:35] + "..." if len(theme) > 35 else theme
        
        return f"[{status.upper()[:3]}] {job_id[:8]}... | {theme_short} | {progress:.1f}%"
    
    def parse_job_id_from_label(self, label: str) -> str:
        """Extract job_id from formatted label."""
        try:
            # Extract job_id from label format: "[STA] 12345678... | theme | progress"
            parts = label.split("] ")
            if len(parts) > 1:
                job_part = parts[1].split(" | ")[0]
                return job_part.replace("...", "")
        except Exception:
            pass
        return label
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """Get generation statistics and system status."""
        health = self.get_health()
        jobs = self.list_jobs()
        
        active_count = len([j for j in jobs if j.get("status") in ["started", "processing"]])
        completed_count = len([j for j in jobs if j.get("status") == "completed"])
        failed_count = len([j for j in jobs if j.get("status") == "failed"])
        
        return {
            "system_status": health.get("status", "unknown"),
            "system_version": health.get("version", "unknown"),
            "jobs": {
                "active": active_count,
                "completed": completed_count,
                "failed": failed_count,
                "total": len(jobs)
            },
            "features": health.get("features", {}),
            "models": health.get("models", {})
        }

"""Enhanced API Client for Sleep Stories AI with Server-Sent Events support.
Updated: normalize base_url, fix SSE URL build, and add logging.
"""

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
        raw = base_url or os.getenv("API_URL", "http://backend:8000/api")
        # Normalize base_url to avoid trailing slashes that may cause // in paths
        self.base_url = raw.rstrip("/")
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
        result = self._make_request("GET", "/models/ollama")
        return result if isinstance(result, list) else []
    
    def get_model_presets(self) -> Dict[str, Any]:
        return self._make_request("GET", "/models/presets") or {}
    
    def get_health(self) -> Dict[str, Any]:
        return self._make_request("GET", "/health/enhanced") or {}
    
    def list_jobs(self) -> List[Dict[str, Any]]:
        result = self._make_request("GET", "/jobs")
        return result.get("jobs", []) if result else []
    
    def get_active_jobs(self) -> List[Dict[str, Any]]:
        all_jobs = self.list_jobs()
        return [j for j in all_jobs if j.get("status") in ["started", "processing", "queued"]]
    
    def start_generation(self, payload: Dict[str, Any]) -> Optional[str]:
        result = self._make_request("POST", "/generate/story", json=payload)
        return result.get("job_id") if result else None
    
    def get_job_telemetry(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._make_request("GET", f"/generate/{job_id}/telemetry")
    
    def get_job_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._make_request("GET", f"/generate/{job_id}/result")
    
    def stream_job_progress(self, job_id: str) -> Generator[Dict[str, Any], None, None]:
        """Stream job progress using Server-Sent Events with fallback."""
        try:
            url = f"{self.base_url}/generate/{job_id}/stream"
            logger.info(f"Opening SSE stream: {url}")
            headers = {'Accept': 'text/event-stream', 'Cache-Control': 'no-cache'}
            with requests.get(url, headers=headers, stream=True, timeout=60) as response:
                if response.status_code != 200:
                    logger.error(f"Stream failed: {response.status_code}")
                    # Fallback immediately to polling
                    yield from self._fallback_polling(job_id)
                    return
                client = sseclient.SSEClient(response)
                for event in client.events():
                    try:
                        if event.data.strip():
                            data = json.loads(event.data)
                            yield data
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.error(f"Event processing error: {e}")
                        continue
        except requests.exceptions.RequestException as e:
            logger.error(f"Streaming error: {e}")
            yield from self._fallback_polling(job_id)
    
    def _fallback_polling(self, job_id: str) -> Generator[Dict[str, Any], None, None]:
        logger.info("Falling back to polling mode for telemetry")
        backoff = 1.5
        max_backoff = 6
        while True:
            telemetry = self.get_job_telemetry(job_id)
            if telemetry:
                yield telemetry
                status = telemetry.get("status")
                if status in ["completed", "failed"]:
                    break
            time.sleep(backoff)
            backoff = min(max_backoff, backoff * 1.3)
    
    def format_job_label(self, job: Dict[str, Any]) -> str:
        job_id = job.get("job_id", "unknown")
        theme = job.get("theme", "No theme")
        progress = job.get("progress", 0)
        status = job.get("status", "unknown")
        theme_short = theme[:35] + "..." if len(theme) > 35 else theme
        return f"[{status.upper()[:3]}] {job_id[:8]}... | {theme_short} | {progress:.1f}%"
    
    def parse_job_id_from_label(self, label: str) -> str:
        try:
            parts = label.split("] ")
            if len(parts) > 1:
                job_part = parts[1].split(" | ")[0]
                return job_part.replace("...", "")
        except Exception:
            pass
        return label
    
    def get_generation_stats(self) -> Dict[str, Any]:
        health = self.get_health()
        jobs = self.list_jobs()
        return {
            "system_status": health.get("status", "unknown"),
            "system_version": health.get("version", "unknown"),
            "jobs": {
                "active": len([j for j in jobs if j.get("status") in ["started", "processing"]]),
                "completed": len([j for j in jobs if j.get("status") == "completed"]),
                "failed": len([j for j in jobs if j.get("status") == "failed"]),
                "total": len(jobs)
            },
            "features": health.get("features", {}),
            "models": health.get("models", {})
        }

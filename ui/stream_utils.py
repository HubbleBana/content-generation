"""Streaming Utilities for Sleep Stories AI UI v2.0

Provides specialized classes and functions for handling real-time streaming
from the backend API using Server-Sent Events (SSE).

By Jimmy - Frontend Expert
"""

import asyncio
import aiohttp
import json
import time
import logging
from typing import Dict, Any, Optional, AsyncGenerator, Callable
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class StreamingError(Exception):
    """Custom exception for streaming-related errors"""
    pass

class ProgressFormatter:
    """Formats progress updates into user-friendly displays"""
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format seconds into human-readable duration"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    @staticmethod
    def format_progress_bar(progress: float, width: int = 40) -> str:
        """Create ASCII progress bar"""
        filled = int(progress * width / 100)
        bar = '█' * filled + '░' * (width - filled)
        return f"[{bar}] {progress:.1f}%"
    
    @staticmethod
    def format_beat_info(beat_data: Dict[str, Any]) -> str:
        """Format beat information for display"""
        if not beat_data:
            return ""
            
        index = beat_data.get("index", 0)
        total = beat_data.get("total", 0)
        stage = beat_data.get("stage", "")
        stage_progress = beat_data.get("stage_progress", 0)
        
        if total > 0:
            return f"Beat {index}/{total} - {stage} ({stage_progress}%)"
        return ""

class EnhancedSSEClient:
    """Enhanced Server-Sent Events client with reconnection and error handling"""
    
    def __init__(self, base_url: str, job_id: str, max_retries: int = 3):
        self.base_url = base_url
        self.job_id = job_id
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None
        self.retry_count = 0
        self.last_event_time = time.time()
        
    async def __aenter__(self):
        """Async context manager entry"""
        timeout = aiohttp.ClientTimeout(total=None, sock_read=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
            
    async def stream_events(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream Server-Sent Events with automatic reconnection"""
        url = f"{self.base_url}/generate/{self.job_id}/stream"
        
        while self.retry_count <= self.max_retries:
            try:
                logger.info(f"Connecting to SSE stream: {url}")
                
                async with self.session.get(url) as response:
                    if response.status != 200:
                        raise StreamingError(f"HTTP {response.status}: {await response.text()}")
                    
                    logger.info("SSE stream connected successfully")
                    self.retry_count = 0  # Reset retry count on successful connection
                    
                    async for line in response.content:
                        line_str = line.decode('utf-8').strip()
                        
                        if not line_str:
                            continue
                            
                        # Handle Server-Sent Events format
                        if line_str.startswith('data: '):
                            try:
                                data = json.loads(line_str[6:])  # Remove 'data: ' prefix
                                self.last_event_time = time.time()
                                yield data
                                
                                # Check if job is complete
                                if data.get('status') in ['completed', 'failed']:
                                    logger.info(f"Job {self.job_id} finished with status: {data.get('status')}")
                                    return
                                    
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse SSE data: {line_str[:100]}... Error: {e}")
                                continue
                                
                        elif line_str.startswith('event: '):
                            event_type = line_str[7:]
                            if event_type == 'heartbeat':
                                self.last_event_time = time.time()
                                yield {"heartbeat": True}
                            elif event_type == 'error':
                                yield {"error": "Server reported error event"}
                                return
                                
                        # Check for connection timeout
                        if time.time() - self.last_event_time > 60:  # 60 second timeout
                            logger.warning("No events received for 60 seconds, reconnecting...")
                            break
                            
            except (aiohttp.ClientError, asyncio.TimeoutError, StreamingError) as e:
                self.retry_count += 1
                logger.error(f"SSE stream error (attempt {self.retry_count}/{self.max_retries}): {e}")
                
                if self.retry_count > self.max_retries:
                    yield {"error": f"Max retries exceeded. Last error: {str(e)}"}
                    return
                    
                # Exponential backoff
                wait_time = min(2 ** self.retry_count, 16)
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Unexpected error in SSE stream: {e}")
                yield {"error": f"Unexpected streaming error: {str(e)}"}
                return

class JobStatusManager:
    """Manages job status and provides formatted updates"""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.start_time = time.time()
        self.last_progress = -1
        self.formatter = ProgressFormatter()
        
    def should_update_display(self, new_progress: float, force: bool = False) -> bool:
        """Determine if display should be updated based on progress change"""
        if force:
            return True
            
        # Update if progress changed by at least 1% or if it's been more than 5 seconds
        progress_changed = abs(new_progress - self.last_progress) >= 1
        return progress_changed
        
    def format_status_update(self, update_data: Dict[str, Any]) -> Dict[str, str]:
        """Format a status update into display-ready content"""
        progress = update_data.get("progress", 0)
        current_step = update_data.get("current_step", "Processing...")
        step_number = update_data.get("current_step_number", 0)
        total_steps = update_data.get("total_steps", 8)
        status = update_data.get("status", "processing")
        beat_info = update_data.get("beat", {})
        timing = update_data.get("timing", {})
        models = update_data.get("models", {})
        
        # Calculate elapsed time
        elapsed_seconds = time.time() - self.start_time
        elapsed_str = self.formatter.format_duration(elapsed_seconds)
        
        # Format ETA if available
        eta_str = ""
        if timing.get("eta_sec"):
            eta_str = f" | ETA: {self.formatter.format_duration(timing['eta_sec'])}"
        
        # Format beat information
        beat_text = self.formatter.format_beat_info(beat_info)
        
        # Format models in use
        model_text = ""
        if models:
            generator = models.get("generator", "")
            reasoner = models.get("reasoner", "")
            polisher = models.get("polisher", "")
            model_parts = []
            if generator:
                model_parts.append(f"Gen: {generator}")
            if reasoner:
                model_parts.append(f"Reason: {reasoner}")
            if polisher:
                model_parts.append(f"Polish: {polisher}")
            if model_parts:
                model_text = f"<p><strong>Models:</strong> {' | '.join(model_parts)}</p>"
        
        # Determine status color and icon
        if status == "completed":
            bg_color = "background: linear-gradient(135deg, #28a745 0%, #20c997 100%);"
            icon = "✅"
            title = "Generation Complete!"
        elif status == "failed":
            bg_color = "background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);"
            icon = "❌"
            title = "Generation Failed"
        else:
            bg_color = "background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);"
            icon = "🚀"
            title = "Generation In Progress"
        
        # Build HTML content
        html_content = f"""
        <div class='status-container' style='{bg_color}'>
            <h3>{icon} {title}</h3>
            <p><strong>Job ID:</strong> <code>{self.job_id}</code></p>
            <p><strong>Step {step_number}/{total_steps}:</strong> {current_step}</p>
        """
        
        if beat_text:
            html_content += f"<p><strong>Current Beat:</strong> {beat_text}</p>"
            
        html_content += model_text
        
        html_content += f"""
            <p><strong>Elapsed:</strong> {elapsed_str}{eta_str}</p>
            <div class='progress-bar'>
                <div class='progress-fill' style='width: {progress}%'></div>
            </div>
            <p style='text-align: center; margin-top: 10px; font-size: 1.2em;'><strong>{progress:.1f}%</strong></p>
        </div>
        """
        
        # Update last progress
        self.last_progress = progress
        
        return {
            "html": html_content,
            "progress": progress,
            "status": status,
            "step": current_step
        }

async def stream_job_with_formatting(
    api_url: str, 
    job_id: str, 
    progress_callback: Optional[Callable[[Dict[str, str]], None]] = None
) -> AsyncGenerator[Dict[str, str], None]:
    """High-level streaming function with automatic formatting"""
    
    status_manager = JobStatusManager(job_id)
    
    try:
        async with EnhancedSSEClient(api_url, job_id) as client:
            async for update in client.stream_events():
                
                # Handle errors
                if "error" in update:
                    error_content = {
                        "html": f"""
                        <div class='status-container' style='background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);'>
                            <h3>❌ Streaming Error</h3>
                            <p><strong>Job ID:</strong> <code>{job_id}</code></p>
                            <p><strong>Error:</strong> {update['error']}</p>
                            <p>Please check your connection and try again.</p>
                        </div>
                        """,
                        "progress": 0,
                        "status": "error",
                        "step": "Error occurred"
                    }
                    yield error_content
                    break
                
                # Skip heartbeats
                if "heartbeat" in update:
                    continue
                
                # Format and yield status update
                progress = update.get("progress", 0)
                if status_manager.should_update_display(progress):
                    formatted_update = status_manager.format_status_update(update)
                    
                    if progress_callback:
                        progress_callback(formatted_update)
                        
                    yield formatted_update
                
                # Break on completion
                if update.get("status") in ["completed", "failed"]:
                    break
                    
    except Exception as e:
        logger.error(f"Error in stream_job_with_formatting: {e}")
        yield {
            "html": f"""
            <div class='status-container' style='background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);'>
                <h3>❌ Streaming Failed</h3>
                <p><strong>Job ID:</strong> <code>{job_id}</code></p>
                <p><strong>Error:</strong> {str(e)}</p>
            </div>
            """,
            "progress": 0,
            "status": "error",
            "step": "Streaming failed"
        }

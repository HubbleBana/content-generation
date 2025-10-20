"""Enhanced Sleep Stories AI Interface v2.0 - By Jimmy

Features:
- Real-time Server-Sent Events streaming (no more polling!)
- Complete parameter coverage for all API endpoints 
- Modern Gradio 5.x components and design
- Automatic job recovery and session management
- Enhanced telemetry and progress visualization
"""

import gradio as gr
import requests
import json
import asyncio
import aiohttp
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Configuration
API_URL = os.getenv("API_URL", "http://backend:8000/api")
REFRESH_INTERVAL = 2  # seconds

class StreamingClient:
    """Handles Server-Sent Events streaming from backend"""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.session = None
        
    async def stream_updates(self):
        """Stream real-time updates using Server-Sent Events"""
        try:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None))
            url = f"{API_URL}/generate/{self.job_id}/stream"
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    yield {"error": f"Stream failed: {response.status}"}
                    return
                    
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])  # Remove 'data: ' prefix
                            yield data
                        except json.JSONDecodeError:
                            continue
                    elif line.startswith('event: heartbeat'):
                        # Send heartbeat to keep connection alive
                        yield {"heartbeat": True}
                        
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield {"error": str(e)}
        finally:
            if self.session:
                await self.session.close()
                
class APIClient:
    """Centralized API client with error handling"""
    
    @staticmethod
    def get(endpoint: str, timeout: int = 20) -> Optional[Dict]:
        """GET request with error handling"""
        try:
            response = requests.get(f"{API_URL}{endpoint}", timeout=timeout)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"GET {endpoint} failed: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"GET {endpoint} error: {e}")
            return None
            
    @staticmethod
    def post(endpoint: str, data: Dict, timeout: int = 30) -> Optional[Dict]:
        """POST request with error handling"""
        try:
            response = requests.post(
                f"{API_URL}{endpoint}", 
                json=data, 
                timeout=timeout,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"POST {endpoint} failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"POST {endpoint} error: {e}")
            return None

def load_jobs() -> List[Dict]:
    """Load all jobs from API"""
    jobs_data = APIClient.get("/jobs")
    if jobs_data and "jobs" in jobs_data:
        return jobs_data["jobs"]
    return []

def format_job_dropdown(jobs: List[Dict]) -> List[str]:
    """Format jobs for dropdown display"""
    formatted = []
    for job in jobs:
        job_id = job.get("job_id", "unknown")
        theme = job.get("theme", "Unknown Theme")[:40]
        status = job.get("status", "unknown")
        progress = job.get("progress", 0)
        created = job.get("created_at", "")
        
        # Format timestamp
        try:
            if created:
                dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                time_str = dt.strftime("%H:%M")
            else:
                time_str = "--:--"
        except:
            time_str = "--:--"
            
        # Create display string
        display = f"{job_id[:8]}... | {theme} | {status.title()} ({progress:.0f}%) | {time_str}"
        formatted.append(display)
        
    return formatted

def extract_job_id(dropdown_value: str) -> str:
    """Extract job ID from dropdown selection"""
    if not dropdown_value:
        return ""
    return dropdown_value.split(" | ")[0].replace("...", "")

def load_available_models() -> List[str]:
    """Load available models from Ollama"""
    models_data = APIClient.get("/models/ollama")
    if isinstance(models_data, list):
        return [model.get("name", "") for model in models_data if isinstance(model, dict)]
    return ["qwen2.5:7b", "deepseek-r1:8b", "mistral:7b"]  # Fallback

def load_model_presets() -> Dict:
    """Load model presets from API"""
    presets_data = APIClient.get("/models/presets")
    if presets_data:
        return presets_data.get("presets", {})
    return {
        "quality_high": {
            "generator": "qwen2.5:7b",
            "reasoner": "deepseek-r1:8b", 
            "polisher": "mistral:7b"
        },
        "fast": {
            "generator": "qwen2.5:7b"
        }
    }

def create_enhanced_ui():
    """Create the enhanced Gradio interface"""
    
    # Custom CSS for modern styling
    custom_css = """
    .status-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px;
        padding: 20px;
        color: white;
        font-family: 'Monaco', 'Menlo', monospace;
    }
    .metric-card {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 15px;
        margin: 5px 0;
    }
    .progress-bar {
        background: #e9ecef;
        border-radius: 10px;
        overflow: hidden;
        height: 20px;
    }
    .progress-fill {
        background: linear-gradient(90deg, #28a745, #20c997);
        height: 100%;
        transition: width 0.3s ease;
    }
    """
    
    with gr.Blocks(
        title="Sleep Stories AI v2.0 - Enhanced by Jimmy",
        theme=gr.themes.Soft(),
        css=custom_css
    ) as interface:
        
        # Header
        gr.HTML("""
        <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; margin-bottom: 20px;">
            <h1 style="color: white; margin: 0; font-size: 2.5em;">🌙 Sleep Stories AI v2.0</h1>
            <p style="color: #e8e9ea; margin: 10px 0 0 0; font-size: 1.2em;">Enhanced by Jimmy - Real-time Streaming & Complete API Coverage</p>
        </div>
        """)
        
        # State variables for tracking
        current_job_id = gr.State("")
        streaming_active = gr.State(False)
        
        with gr.Row():
            with gr.Column(scale=1):
                # === BASIC SETTINGS ===
                with gr.Group():
                    gr.Markdown("### 🎯 Story Configuration")
                    theme = gr.Textbox(
                        label="Theme/Setting",
                        placeholder="e.g., Moonlit forest path, Scottish Highland lake...",
                        value="Peaceful mountain meadow at dawn"
                    )
                    description = gr.Textbox(
                        label="Additional Details (optional)",
                        placeholder="e.g., Focus on gentle morning sounds and soft light...",
                        lines=3
                    )
                    duration = gr.Slider(
                        minimum=10,
                        maximum=120,
                        value=45,
                        step=5,
                        label="Duration (minutes)"
                    )
                
                # === MODEL CONFIGURATION ===
                with gr.Group():
                    gr.Markdown("### 🤖 AI Model Configuration")
                    
                    with gr.Row():
                        use_preset = gr.Checkbox(label="Use Preset", value=True)
                        preset_dropdown = gr.Dropdown(
                            choices=list(load_model_presets().keys()),
                            value="quality_high",
                            label="Model Preset"
                        )
                    
                    with gr.Accordion("Custom Models", open=False):
                        available_models = load_available_models()
                        generator_model = gr.Dropdown(
                            choices=available_models,
                            value="qwen2.5:7b",
                            label="Generator Model",
                            allow_custom_value=True
                        )
                        reasoner_model = gr.Dropdown(
                            choices=available_models,
                            value="deepseek-r1:8b", 
                            label="Reasoner Model",
                            allow_custom_value=True
                        )
                        polisher_model = gr.Dropdown(
                            choices=available_models,
                            value="mistral:7b",
                            label="Polisher Model", 
                            allow_custom_value=True
                        )
                    
                    use_reasoner = gr.Checkbox(label="Enable Reasoner", value=True)
                    use_polisher = gr.Checkbox(label="Enable Polisher", value=True)
                
                # === QUALITY & OUTPUT SETTINGS ===
                with gr.Group():
                    gr.Markdown("### ⚙️ Quality & Output Settings")
                    
                    tts_markers = gr.Checkbox(label="Insert TTS Markers", value=False)
                    strict_schema = gr.Checkbox(label="Structured JSON Output", value=False)
                    sensory_rotation = gr.Checkbox(label="Sensory Rotation", value=True)
                    sleep_taper = gr.Checkbox(label="Sleep Taper Effect", value=True)
                    
                    with gr.Accordion("Advanced Parameters", open=False):
                        model_temperature = gr.Slider(
                            minimum=0.1,
                            maximum=1.5,
                            value=0.7,
                            step=0.05,
                            label="Model Temperature"
                        )
                        beats_count = gr.Slider(
                            minimum=6,
                            maximum=20,
                            value=12,
                            step=1,
                            label="Story Beats Count"
                        )
                        words_per_beat = gr.Slider(
                            minimum=400,
                            maximum=800,
                            value=600,
                            step=50,
                            label="Words Per Beat"
                        )
                        tolerance = gr.Slider(
                            minimum=0.1,
                            maximum=0.5,
                            value=0.2,
                            step=0.05,
                            label="Word Count Tolerance"
                        )
                
                # === ACTION BUTTONS ===
                with gr.Group():
                    gr.Markdown("### 🚀 Actions")
                    with gr.Row():
                        generate_btn = gr.Button(
                            "🎬 Generate Story",
                            variant="primary",
                            size="lg"
                        )
                        stop_btn = gr.Button(
                            "⏹️ Stop",
                            variant="secondary",
                            size="lg"
                        )
                    
                    refresh_models_btn = gr.Button(
                        "🔄 Refresh Models",
                        variant="secondary"
                    )
                    
            with gr.Column(scale=2):
                # === JOB MANAGEMENT ===
                with gr.Group():
                    gr.Markdown("### 📋 Session Management")
                    with gr.Row():
                        jobs_dropdown = gr.Dropdown(
                            choices=format_job_dropdown(load_jobs()),
                            label="Active/Recent Jobs",
                            allow_custom_value=False,
                            scale=3
                        )
                        refresh_jobs_btn = gr.Button("🔄", size="sm", scale=1)
                        attach_btn = gr.Button("🔗 Attach", variant="secondary", scale=1)
                
                # === REAL-TIME STATUS ===
                with gr.Group():
                    gr.Markdown("### 📊 Real-time Status & Progress")
                    status_display = gr.HTML(
                        value="<div class='status-container'>Ready to generate stories...</div>",
                        elem_classes=["status-container"]
                    )
                    
                # === OUTPUT TABS ===
                with gr.Tabs() as output_tabs:
                    with gr.Tab("📖 Story Text"):
                        story_output = gr.Textbox(
                            lines=20,
                            show_copy_button=True,
                            interactive=False,
                            placeholder="Generated story will appear here..."
                        )
                    
                    with gr.Tab("📈 Metrics & Analytics"):
                        metrics_output = gr.JSON(
                            label="Generation Metrics",
                            value={"status": "No metrics available"}
                        )
                    
                    with gr.Tab("🏗️ Story Structure"):
                        outline_output = gr.JSON(
                            label="Story Outline", 
                            value={"status": "No outline available"}
                        )
                    
                    with gr.Tab("🔧 Technical Schema"):
                        schema_output = gr.JSON(
                            label="Beats Schema",
                            value={"status": "No schema available"}
                        )
                    
                    with gr.Tab("🔍 Debug Info"):
                        debug_output = gr.JSON(
                            label="Debug Information",
                            value={"api_url": API_URL, "status": "Ready"}
                        )
        
        # === EVENT HANDLERS ===
        
        def refresh_jobs():
            """Refresh the jobs dropdown"""
            jobs = load_jobs()
            return gr.update(choices=format_job_dropdown(jobs), value=None)
            
        def refresh_models():
            """Refresh available models"""
            models = load_available_models()
            return [
                gr.update(choices=models),
                gr.update(choices=models), 
                gr.update(choices=models)
            ]
            
        def build_generation_payload(
            theme, description, duration, use_preset, preset_name,
            generator, reasoner, polisher, use_reasoner, use_polisher,
            tts_markers, strict_schema, sensory_rotation, sleep_taper,
            temperature, beats, words_per_beat, tolerance
        ):
            """Build the payload for story generation"""
            payload = {
                "theme": theme,
                "description": description if description.strip() else None,
                "duration": int(duration),
                "use_reasoner": use_reasoner,
                "use_polish": use_polisher,
                "tts_markers": tts_markers,
                "strict_schema": strict_schema,
                "sensory_rotation": sensory_rotation,
                "sleep_taper": sleep_taper,
                "temps": {
                    "generator": temperature,
                    "reasoner": temperature * 0.5,
                    "polisher": temperature * 0.6
                },
                "beats": int(beats),
                "words_per_beat": int(words_per_beat),
                "tolerance": tolerance
            }
            
            # Model configuration
            if not use_preset:
                payload["models"] = {
                    "generator": generator,
                    "reasoner": reasoner if use_reasoner else None,
                    "polisher": polisher if use_polisher else None
                }
            else:
                presets = load_model_presets()
                if preset_name in presets:
                    payload["models"] = presets[preset_name]
                    
            return payload
            
        def start_generation(*args):
            """Start story generation and return job ID"""
            payload = build_generation_payload(*args)
            
            # Start generation
            result = APIClient.post("/generate/story", payload)
            if result and "job_id" in result:
                job_id = result["job_id"]
                status_html = f"""
                <div class='status-container'>
                    <h3>🚀 Generation Started!</h3>
                    <p><strong>Job ID:</strong> {job_id}</p>
                    <p><strong>Theme:</strong> {payload['theme']}</p>
                    <p><strong>Status:</strong> Initializing...</p>
                    <div class='progress-bar'>
                        <div class='progress-fill' style='width: 0%'></div>
                    </div>
                </div>
                """
                return job_id, True, status_html, "", {}, {}, {}
            else:
                error_html = """
                <div class='status-container' style='background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);'>
                    <h3>❌ Generation Failed</h3>
                    <p>Failed to start generation. Please check API connection.</p>
                </div>
                """
                return "", False, error_html, "", {}, {}, {}
        
        async def stream_job_updates(job_id: str):
            """Stream job updates using Server-Sent Events"""
            if not job_id:
                return
                
            client = StreamingClient(job_id)
            last_progress = -1
            
            async for update in client.stream_updates():
                if "error" in update:
                    yield (
                        f"""
                        <div class='status-container' style='background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);'>
                            <h3>❌ Streaming Error</h3>
                            <p>{update['error']}</p>
                        </div>
                        """,
                        "", {}, {}, {}
                    )
                    break
                    
                if "heartbeat" in update:
                    continue
                    
                # Format progress update
                progress = update.get("progress", 0)
                current_step = update.get("current_step", "Processing...")
                step_number = update.get("current_step_number", 0)
                total_steps = update.get("total_steps", 8)
                status = update.get("status", "processing")
                beat_info = update.get("beat", {})
                timing = update.get("timing", {})
                
                # Only update if progress changed significantly
                if abs(progress - last_progress) >= 1 or status in ["completed", "failed"]:
                    last_progress = progress
                    
                    # Format beat information
                    beat_text = ""
                    if beat_info:
                        beat_index = beat_info.get("index", 0)
                        beat_total = beat_info.get("total", 0)
                        beat_stage = beat_info.get("stage", "")
                        if beat_total > 0:
                            beat_text = f"<p><strong>Beat:</strong> {beat_index}/{beat_total} - {beat_stage}</p>"
                    
                    # Format timing information
                    timing_text = ""
                    elapsed = timing.get("elapsed_sec", 0)
                    eta = timing.get("eta_sec")
                    if elapsed > 0:
                        elapsed_str = str(timedelta(seconds=int(elapsed)))
                        timing_text = f"<p><strong>Elapsed:</strong> {elapsed_str}"
                        if eta:
                            eta_str = str(timedelta(seconds=int(eta)))
                            timing_text += f" | <strong>ETA:</strong> {eta_str}"
                        timing_text += "</p>"
                    
                    # Create status HTML
                    if status == "completed":
                        status_html = f"""
                        <div class='status-container' style='background: linear-gradient(135deg, #28a745 0%, #20c997 100%);'>
                            <h3>✅ Generation Complete!</h3>
                            <p><strong>Job ID:</strong> {job_id}</p>
                            <p><strong>Final Step:</strong> {current_step}</p>
                            {timing_text}
                            <div class='progress-bar'>
                                <div class='progress-fill' style='width: 100%'></div>
                            </div>
                        </div>
                        """
                        
                        # Fetch final results
                        result = APIClient.get(f"/generate/{job_id}/result")
                        if result:
                            story = result.get("story_text", "")
                            metrics = result.get("metrics", {})
                            outline = result.get("outline", {})
                            schema = result.get("beats_schema", {})
                            
                            yield (status_html, story, metrics, outline, schema)
                        else:
                            yield (status_html, "", {}, {}, {})
                        break
                        
                    elif status == "failed":
                        error_msg = update.get("error", "Unknown error")
                        status_html = f"""
                        <div class='status-container' style='background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);'>
                            <h3>❌ Generation Failed</h3>
                            <p><strong>Job ID:</strong> {job_id}</p>
                            <p><strong>Error:</strong> {error_msg}</p>
                            {timing_text}
                        </div>
                        """
                        yield (status_html, "", {}, {}, {})
                        break
                        
                    else:
                        status_html = f"""
                        <div class='status-container'>
                            <h3>🚀 Generation In Progress</h3>
                            <p><strong>Job ID:</strong> {job_id}</p>
                            <p><strong>Step {step_number}/{total_steps}:</strong> {current_step}</p>
                            {beat_text}
                            {timing_text}
                            <div class='progress-bar'>
                                <div class='progress-fill' style='width: {progress}%'></div>
                            </div>
                            <p style='text-align: center; margin-top: 10px;'><strong>{progress:.1f}%</strong></p>
                        </div>
                        """
                        yield (status_html, "", {}, {}, {})
        
        def attach_to_job(dropdown_selection):
            """Attach to existing job"""
            job_id = extract_job_id(dropdown_selection)
            if not job_id:
                return "", False, "<div class='status-container'>Please select a job to attach to.</div>", "", {}, {}, {}
            
            # Check if job exists and get current status
            telemetry = APIClient.get(f"/generate/{job_id}/telemetry")
            if not telemetry:
                return "", False, f"<div class='status-container'>Job {job_id} not found or inaccessible.</div>", "", {}, {}, {}
            
            status_html = f"""
            <div class='status-container'>
                <h3>🔗 Attached to Job</h3>
                <p><strong>Job ID:</strong> {job_id}</p>
                <p><strong>Status:</strong> {telemetry.get('status', 'unknown').title()}</p>
                <p>Streaming updates will appear here...</p>
            </div>
            """
            
            return job_id, True, status_html, "", {}, {}, {}
        
        # Wire up event handlers
        refresh_jobs_btn.click(
            refresh_jobs,
            outputs=[jobs_dropdown]
        )
        
        refresh_models_btn.click(
            refresh_models,
            outputs=[generator_model, reasoner_model, polisher_model]
        )
        
        generate_btn.click(
            start_generation,
            inputs=[
                theme, description, duration, use_preset, preset_dropdown,
                generator_model, reasoner_model, polisher_model,
                use_reasoner, use_polisher, tts_markers, strict_schema,
                sensory_rotation, sleep_taper, model_temperature, beats_count,
                words_per_beat, tolerance
            ],
            outputs=[
                current_job_id, streaming_active, status_display,
                story_output, metrics_output, outline_output, schema_output
            ]
        ).then(
            stream_job_updates,
            inputs=[current_job_id],
            outputs=[status_display, story_output, metrics_output, outline_output, schema_output]
        )
        
        attach_btn.click(
            attach_to_job,
            inputs=[jobs_dropdown],
            outputs=[
                current_job_id, streaming_active, status_display,
                story_output, metrics_output, outline_output, schema_output
            ]
        ).then(
            stream_job_updates,
            inputs=[current_job_id],
            outputs=[status_display, story_output, metrics_output, outline_output, schema_output]
        )
        
        # Auto-refresh jobs on load
        interface.load(
            lambda: [
                format_job_dropdown(load_jobs()),
                load_available_models(),
                load_available_models(),
                load_available_models()
            ],
            outputs=[jobs_dropdown, generator_model, reasoner_model, polisher_model]
        )
        
    return interface

if __name__ == "__main__":
    # Create and launch the enhanced interface
    demo = create_enhanced_ui()
    demo.queue(max_size=20)  # Enable queueing for concurrent requests
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
        show_api=False,  # Hide API docs for cleaner interface
        max_threads=50
    )

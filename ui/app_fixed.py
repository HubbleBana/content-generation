import gradio as gr
import requests
import json
import time
import os
from typing import Optional, Generator
from datetime import datetime, timedelta
import threading
import queue
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = os.getenv("API_URL", "http://backend:8000/api")

class ImprovedSSEClient:
    """Improved SSE Client with better timeout handling and error recovery."""
    
    def __init__(self, url: str, timeout: int = 300):
        self.url = url
        self.timeout = timeout
        self.session = requests.Session()
        # Set appropriate timeouts
        self.session.timeout = (10, timeout)  # (connection, read) timeouts
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()
        
    def events(self) -> Generator[dict, None, None]:
        """Generator that yields SSE events with improved error handling."""
        try:
            headers = {
                'Accept': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            }
            
            logger.info(f"Starting SSE stream to {self.url}")
            
            with self.session.get(
                self.url, 
                stream=True, 
                headers=headers,
                timeout=(10, self.timeout)  # 10s connection, 5min read
            ) as response:
                
                response.raise_for_status()
                logger.info(f"SSE connection established, status: {response.status_code}")
                
                for line in response.iter_lines(decode_unicode=True, chunk_size=1024):
                    if not line:
                        continue
                        
                    line = line.strip()
                    
                    if line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])
                            yield data
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to decode JSON: {line[6:]}")
                            continue
                            
                    elif line.startswith('event: heartbeat'):
                        # Heartbeat - just continue
                        continue
                        
                    elif line.startswith('event: '):
                        # Other event types
                        logger.debug(f"Received event: {line}")
                        
        except requests.exceptions.Timeout as e:
            logger.error(f"SSE stream timeout: {e}")
            yield {"status": "error", "message": "Stream timeout - connection lost"}
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"SSE connection error: {e}")
            yield {"status": "error", "message": "Connection error - retrying..."}
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"SSE HTTP error: {e}")
            yield {"status": "error", "message": f"Server error: {e.response.status_code}"}
            
        except Exception as e:
            logger.error(f"Unexpected SSE error: {e}")
            yield {"status": "error", "message": f"Unexpected error: {str(e)}"}

# --- Backend integrations with improved timeout handling ---

def fetch_ollama_models():
    """Fetch available Ollama models with proper timeout."""
    try:
        r = requests.get(f"{API_URL}/models/ollama", timeout=8)
        if r.status_code == 200:
            models = r.json()
            return [m.get("name", "unknown") for m in models]
    except requests.exceptions.Timeout:
        logger.warning("Timeout fetching Ollama models")
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
    return []

def test_backend_connection():
    """Test backend connection and return status."""
    try:
        r = requests.get(f"{API_URL}/health/enhanced", timeout=5)
        if r.status_code == 200:
            return True, "Backend connected"
        else:
            return False, f"Backend error: {r.status_code}"
    except requests.exceptions.Timeout:
        return False, "Backend timeout (>5s)"
    except Exception as e:
        return False, f"Backend unreachable: {str(e)}"

# --- Enhanced story generation with improved streaming ---

def generate_enhanced_story_with_streaming(
    theme: str, duration: int, description: Optional[str] = None,
    model_preset: str = "quality_high", use_custom_models: bool = False,
    custom_generator: str = "", custom_reasoner: str = "", custom_polisher: str = "",
    use_reasoner: bool = True, use_polisher: bool = True,
    tts_markers: bool = False, strict_schema: bool = False,
    sensory_rotation: Optional[bool] = None, sleep_taper: Optional[bool] = None,
    custom_waypoints: Optional[list] = None
) -> Generator[tuple, None, None]:
    """Generator function for streaming updates to Gradio."""
    
    start_time = time.time()
    
    # Test backend first
    connected, conn_msg = test_backend_connection()
    if not connected:
        error_msg = f"❌ Backend Error: {conn_msg}\n\nPlease check:"
        error_msg += "\n- Docker containers running (docker-compose ps)"
        error_msg += "\n- Backend logs (docker-compose logs backend)"
        error_msg += "\n- Network connectivity"
        yield (error_msg, "", "", "", "")
        return
    
    # Prepare models
    models_block = None
    if use_custom_models:
        models = {}
        if custom_generator: models["generator"] = custom_generator
        if custom_reasoner: models["reasoner"] = custom_reasoner  
        if custom_polisher: models["polisher"] = custom_polisher
        if models:
            models_block = models
    
    # Prepare payload
    payload = {
        "theme": theme,
        "duration": duration,
        "description": description or None,
        "use_reasoner": use_reasoner,
        "use_polish": use_polisher,
        "tts_markers": tts_markers,
        "strict_schema": strict_schema
    }
    
    if models_block:
        payload["models"] = models_block
    if sensory_rotation is not None:
        payload["sensory_rotation"] = sensory_rotation
    if sleep_taper is not None:
        payload["sleep_taper"] = sleep_taper
    if custom_waypoints:
        payload["custom_waypoints"] = custom_waypoints
    
    logger.info(f"Starting generation with payload: {json.dumps(payload, indent=2)}")
    
    # Start generation job
    try:
        r = requests.post(f"{API_URL}/generate/story", json=payload, timeout=30)
        if r.status_code != 200:
            error_msg = f"❌ Error starting generation: {r.status_code}\n{r.text}"
            yield (error_msg, "", "", "", "")
            return
            
        job = r.json()
        job_id = job.get("job_id")
        
        if not job_id:
            yield ("❌ No job ID returned from backend", "", "", "", "")
            return
            
    except requests.exceptions.Timeout:
        yield ("❌ Timeout starting generation (>30s)", "", "", "", "")
        return
    except Exception as e:
        yield (f"❌ Error starting generation: {str(e)}", "", "", "", "")
        return
    
    def build_status(progress, current_step, step_num, total_steps, elapsed, features, error_msg=None):
        """Build status display string."""
        feats = job.get("features", {}) if features is None else features
        
        # Correct model names
        model_info = "Qwen3-8B + DeepSeek-R1-8B + Mistral-7B" if feats.get('multi_model') else "Single Model"
        
        lines = [
            f"{'🔥' if feats.get('multi_model') else '📦'} Multi-Model: {model_info}",
            f"{'🎯' if feats.get('quality_enhancements') else '📦'} Quality Enhanced: {'YES' if feats.get('quality_enhancements') else 'NO'}",
            f"{'🎤' if feats.get('tts_markers') else '📦'} TTS Markers: {'YES' if feats.get('tts_markers') else 'NO'}",
            f"{'📋' if feats.get('strict_schema') else '📦'} Strict Schema: {'YES' if feats.get('strict_schema') else 'NO'}",
        ]
        
        bar_filled = int(progress / 2.5)
        bar = f"[{'🟩' * bar_filled}{'⬜' * (40 - bar_filled)}] {progress:.1f}%"
        
        status_text = f"""🚀 Enhanced Sleep Stories AI Generator - Fixed v2.3

Job: {job_id}
Preset: {model_preset if not use_custom_models else 'CUSTOM'}
Elapsed: {elapsed}

Features:
- """ + "\n- ".join(lines)
        
        if error_msg:
            status_text += f"\n\n⚠️  WARNING: {error_msg}"
        
        status_text += f"\n\nStatus: PROCESSING\nStep: {step_num}/{total_steps} - {current_step}\n{bar}"
        
        return status_text
    
    # Stream updates
    features = None
    last_status = ""
    error_count = 0
    max_errors = 3
    
    try:
        with ImprovedSSEClient(f"{API_URL}/generate/{job_id}/stream", timeout=600) as sse:
            
            for event in sse.events():
                elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7]
                
                if event.get('status') == 'error':
                    error_count += 1
                    error_msg = event.get('message', 'Unknown streaming error')
                    
                    if error_count >= max_errors:
                        yield (f"❌ Too many streaming errors: {error_msg}", "", "", "", "")
                        return
                    
                    # Show error but continue
                    features = event.get("enhanced_features", features)
                    status_text = build_status(
                        event.get("progress", 0), 
                        event.get("current_step", "Error occurred..."), 
                        event.get("current_step_number", 0), 
                        event.get("total_steps", 8), 
                        elapsed, 
                        features,
                        error_msg
                    )
                    yield (status_text, "", "", "", "")
                    continue
                
                # Reset error count on successful event
                error_count = 0
                
                features = event.get("enhanced_features", features)
                status_text = build_status(
                    event.get("progress", 0),
                    event.get("current_step", "Processing..."),
                    event.get("current_step_number", 0),
                    event.get("total_steps", 8),
                    elapsed,
                    features
                )
                
                # Only yield if status changed (reduce UI flicker)
                if status_text != last_status:
                    yield (status_text, "", "", "", "")
                    last_status = status_text
                
                # Check for completion
                if event.get('status') == 'completed':
                    break
                elif event.get('status') == 'failed':
                    final_status = status_text + "\n\n❌ GENERATION FAILED"
                    yield (final_status, "", "", "", "")
                    return
                    
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        error_status = last_status + f"\n\n⚠️  Streaming interrupted: {str(e)[:100]}"
        yield (error_status, "", "", "", "")
    
    # Get final results
    try:
        logger.info(f"Fetching final results for job {job_id}")
        res = requests.get(f"{API_URL}/generate/{job_id}/result", timeout=30)
        
        if res.status_code != 200:
            elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7]
            error_msg = f"❌ Error getting results after {elapsed}: {res.status_code}\n{res.text[:200]}"
            yield (last_status + "\n\n" + error_msg, "", "", "", "")
            return
            
        data = res.json()
        
    except requests.exceptions.Timeout:
        yield (last_status + "\n\n❌ Timeout fetching results (>30s)", "", "", "", "")
        return
    except Exception as e:
        yield (last_status + f"\n\n❌ Error fetching results: {str(e)}", "", "", "", "")
        return
    
    # Process results
    story_text = data.get('story_text', '')
    metrics = data.get('metrics', {})
    coherence = data.get('coherence_stats', {})
    memory = data.get('memory_stats', {})
    info = data.get('generation_info', {})
    beats_schema = data.get('beats_schema', {})
    
    total_elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7]
    
    # Build metrics text
    metrics_text = (
        "📊 ENHANCED METRICS\n\n"
        f"Total Time: {total_elapsed}\n"
        f"Target Duration: {duration} min\n"
        f"Final Words: {metrics.get('english_word_count', len(story_text.split())):,}\n"
        f"Target Words: {metrics.get('target_words', duration * 150):,}\n"
        f"Accuracy: {metrics.get('accuracy_percent', 0):.1f}% deviation\n\n"
        f"🤖 MODEL PERFORMANCE:\n"
        f"Generator (Qwen3-8B): {metrics.get('generator_words', 0):,} words\n"
        f"Reasoner (DeepSeek-R1): {metrics.get('reasoner_words', 0):,} words\n"
        f"Polisher (Mistral-7B): {metrics.get('polisher_words', 0):,} words\n\n"
        f"📈 QUALITY METRICS:\n"
        f"Corrections Applied: {metrics.get('corrections_count', 0)}\n"
        f"Coherence Improvements: {metrics.get('coherence_improvements', 0)}\n"
        f"Sensory Transitions: {coherence.get('sensory_transitions', 0)}\n"
        f"Average Density Factor: {coherence.get('avg_density_factor', 1.0):.2f}\n"
    )
    
    # Build outline text
    if isinstance(data.get('outline', ''), dict):
        outline_text = json.dumps(data['outline'], indent=2)
    else:
        outline_text = str(data.get('outline', ''))
    
    # Build schema text
    if beats_schema and strict_schema:
        schema_text = json.dumps(beats_schema, indent=2)
    else:
        schema_text = "Strict schema not enabled." if not strict_schema else "No schema data available."
    
    # Final status
    final_status = last_status + f"\n\n✅ COMPLETED in {total_elapsed}!"
    
    yield (final_status, story_text, metrics_text, outline_text, schema_text)

# --- Gradio UI with improved error handling ---

with gr.Blocks(title="Sleep Stories AI - Enhanced v2.3 FIXED", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🌙 Sleep Stories AI - Enhanced v2.3 (STREAMING FIXED)")
    
    # Add connection status
    with gr.Row():
        connection_status = gr.Textbox(label="Backend Status", interactive=False, max_lines=2)
    
    with gr.Row():
        with gr.Column(scale=1):
            theme = gr.Textbox(label="Theme / Setting", value="A tranquil mountain meadow with gentle morning mist")
            description = gr.Textbox(label="Additional Details (optional)", lines=3)
            duration = gr.Slider(20, 90, value=45, step=5, label="Duration (minutes)")
            
            gr.Markdown("### 🤖 Model Selection (Qwen3-8B + DeepSeek-R1-8B + Mistral-7B)")
            with gr.Row():
                generator_dd = gr.Dropdown(choices=[], label="Generator Model (Qwen3-8B)", allow_custom_value=True)
                refresh_gen = gr.Button("↻", size="sm")
            with gr.Row():
                reasoner_dd = gr.Dropdown(choices=[], label="Reasoner Model (DeepSeek-R1-8B)", allow_custom_value=True)
                refresh_r = gr.Button("↻", size="sm")
            with gr.Row():
                polisher_dd = gr.Dropdown(choices=[], label="Polisher Model (Mistral-7B)", allow_custom_value=True)
                refresh_p = gr.Button("↻", size="sm")
            
            use_reasoner = gr.Checkbox(label="Use Reasoner (DeepSeek-R1)", value=True)
            use_polisher = gr.Checkbox(label="Use Polisher (Mistral-7B)", value=True)
            tts_markers = gr.Checkbox(label="Insert TTS Markers", value=False)
            strict_schema = gr.Checkbox(label="Strict JSON Schema", value=False)
            
            gr.Markdown("### 🔧 Advanced Settings (optional)")
            sensory_rotation = gr.Checkbox(label="Override Sensory Rotation")
            sleep_taper = gr.Checkbox(label="Override Sleep Taper")
            custom_waypoints = gr.Textbox(label="Custom Waypoints (comma separated)")
            
            generate_btn = gr.Button("Generate Enhanced Story", variant="primary")
            clear_btn = gr.Button("Clear")
        
        with gr.Column(scale=2):
            status = gr.Textbox(label="Status (Real-time)", lines=16, interactive=False)
            with gr.Tabs():
                with gr.Tab("Story"):
                    story_output = gr.Textbox(lines=26, interactive=False, show_copy_button=True)
                with gr.Tab("Metrics"):
                    metrics_output = gr.Textbox(lines=26, interactive=False, show_copy_button=True)
                with gr.Tab("Outline"):
                    outline_output = gr.Textbox(lines=26, interactive=False, show_copy_button=True)
                with gr.Tab("Schema"):
                    schema_output = gr.Textbox(lines=26, interactive=False, show_copy_button=True)
    
    # Initialize on load
    def init_ui():
        models = fetch_ollama_models()
        connected, conn_msg = test_backend_connection()
        status_msg = f"✅ {conn_msg}" if connected else f"❌ {conn_msg}"
        return (
            gr.update(choices=models),
            gr.update(choices=models), 
            gr.update(choices=models),
            status_msg
        )
    
    demo.load(
        fn=init_ui, 
        inputs=None, 
        outputs=[generator_dd, reasoner_dd, polisher_dd, connection_status]
    )
    
    # Refresh buttons
    refresh_gen.click(
        fn=lambda: gr.update(choices=fetch_ollama_models()), 
        inputs=None, 
        outputs=[generator_dd]
    )
    refresh_r.click(
        fn=lambda: gr.update(choices=fetch_ollama_models()), 
        inputs=None, 
        outputs=[reasoner_dd]
    )
    refresh_p.click(
        fn=lambda: gr.update(choices=fetch_ollama_models()), 
        inputs=None, 
        outputs=[polisher_dd]
    )
    
    # Main generation function
    def handle_generate_streaming(*args):
        """Handle generation with streaming updates."""
        (
            theme, duration, description, generator_model, reasoner_model, polisher_model,
            use_reasoner, use_polisher, tts_markers, strict_schema,
            sensory_rotation, sleep_taper, custom_waypoints
        ) = args
        
        models = {}
        if generator_model: 
            models["generator"] = generator_model
        if use_reasoner and reasoner_model: 
            models["reasoner"] = reasoner_model
        if use_polisher and polisher_model: 
            models["polisher"] = polisher_model
            
        waypoints = [w.strip() for w in custom_waypoints.split(',')] if custom_waypoints else None
        
        # Use streaming generator - yield each update
        for update in generate_enhanced_story_with_streaming(
            theme=theme,
            duration=duration,
            description=description,
            model_preset="custom" if models else "quality_high",
            use_custom_models=bool(models),
            custom_generator=models.get("generator", ""),
            custom_reasoner=models.get("reasoner", ""),
            custom_polisher=models.get("polisher", ""),
            use_reasoner=use_reasoner,
            use_polisher=use_polisher,
            tts_markers=tts_markers,
            strict_schema=strict_schema,
            sensory_rotation=True if sensory_rotation else None,
            sleep_taper=True if sleep_taper else None,
            custom_waypoints=waypoints
        ):
            yield update
    
    # Connect generation button with streaming
    generate_btn.click(
        fn=handle_generate_streaming,
        inputs=[
            theme, duration, description, generator_dd, reasoner_dd, polisher_dd,
            use_reasoner, use_polisher, tts_markers, strict_schema,
            sensory_rotation, sleep_taper, custom_waypoints
        ],
        outputs=[status, story_output, metrics_output, outline_output, schema_output]
    )
    
    # Clear function
    clear_btn.click(
        fn=lambda: ("", "", "", "", ""), 
        inputs=None,
        outputs=[status, story_output, metrics_output, outline_output, schema_output]
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0", 
        server_port=7860, 
        share=False, 
        show_error=True,
        debug=True
    )

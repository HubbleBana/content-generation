import gradio as gr
import requests
import json
import time
import os
from typing import Optional, Generator, Dict, Any
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = os.getenv("API_URL", "http://backend:8000/api")

# --- Backend API Functions ---

def fetch_ollama_models():
    """Fetch available Ollama models with proper timeout."""
    try:
        r = requests.get(f"{API_URL}/models/ollama", timeout=8)
        if r.status_code == 200:
            models = r.json()
            return [m.get("name", "unknown") for m in models]
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
    return []

def fetch_active_jobs():
    """Fetch active jobs for resume functionality."""
    try:
        r = requests.get(f"{API_URL}/jobs", timeout=5)
        if r.status_code == 200:
            jobs_data = r.json()
            jobs = jobs_data.get("jobs", [])
            # Filter active jobs
            active_jobs = [j for j in jobs if j["status"] in ["started", "processing"]]
            return [(f"{j['job_id'][:8]} - {j['theme'][:30]}...", j["job_id"]) for j in active_jobs]
    except Exception as e:
        logger.error(f"Error fetching jobs: {e}")
    return []

def test_backend_connection():
    """Test backend connection and return status."""
    try:
        r = requests.get(f"{API_URL}/health/enhanced", timeout=5)
        if r.status_code == 200:
            return True, "Backend connected - Enhanced v2.0", r.json()
        else:
            return False, f"Backend error: {r.status_code}", None
    except requests.exceptions.Timeout:
        return False, "Backend timeout (>5s)", None
    except Exception as e:
        return False, f"Backend unreachable: {str(e)}", None

def get_model_presets():
    """Get available model presets."""
    try:
        r = requests.get(f"{API_URL}/models/presets", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {"presets": {}, "default_models": {}, "available_features": {}}

# --- Core Generation Functions with Gradio Streaming ---

def start_job_and_stream(
    # Basic parameters
    theme: str, duration: int, description: str,
    
    # Model selection
    use_custom_models: bool, generator_model: str, reasoner_model: str, polisher_model: str,
    use_reasoner: bool, use_polisher: bool,
    
    # Quality parameters
    tts_markers: bool, strict_schema: bool, sensory_rotation: bool, sleep_taper: bool,
    
    # Advanced parameters
    model_temperature: float, target_wpm: int, words_per_beat: int, beats_per_story: int,
    max_tokens_beat: int, max_tokens_outline: int, custom_waypoints: str,
    
    # Sensory settings
    sensory_modes_str: str, opener_penalty_threshold: int, transition_penalty_weight: float,
    redundancy_penalty_weight: float, beat_planning: bool, beat_length_tolerance: float,
    
    # Sleep taper settings
    taper_start_percentage: float, taper_reduction_factor: float,
    
    # TTS settings
    tts_pause_min: float, tts_pause_max: float, tts_breathe_frequency: int
) -> Generator[tuple, None, None]:
    """Start new job and stream progress using Gradio generator pattern."""
    
    start_time = time.time()
    
    # Test backend first
    connected, conn_msg, health_data = test_backend_connection()
    if not connected:
        error_msg = f"❌ Backend Error: {conn_msg}\n\nPlease check:"
        error_msg += "\n- Docker containers running (docker-compose ps)"
        error_msg += "\n- Backend logs (docker-compose logs backend)"
        error_msg += "\n- Network connectivity"
        yield (error_msg, "", "", "", "", "")
        return
    
    # Prepare models
    models_dict = {}
    if use_custom_models:
        if generator_model: models_dict["generator"] = generator_model
        if reasoner_model: models_dict["reasoner"] = reasoner_model
        if polisher_model: models_dict["polisher"] = polisher_model
    
    # Parse custom waypoints
    waypoints = None
    if custom_waypoints.strip():
        waypoints = [w.strip() for w in custom_waypoints.split(',') if w.strip()]
    
    # Parse sensory modes
    sensory_modes = None
    if sensory_modes_str.strip():
        sensory_modes = [m.strip() for m in sensory_modes_str.split(',') if m.strip()]
    
    # Build comprehensive payload
    payload = {
        "theme": theme,
        "duration": duration,
        "description": description or None,
        "use_reasoner": use_reasoner,
        "use_polish": use_polisher,
        "tts_markers": tts_markers,
        "strict_schema": strict_schema,
        "sensory_rotation": sensory_rotation,
        "sleep_taper": sleep_taper,
        
        # Advanced parameters
        "model_temperature": model_temperature,
        "target_wpm": target_wpm,
        "words_per_beat": words_per_beat,
        "beats_per_story": beats_per_story,
        "max_tokens_beat": max_tokens_beat,
        "max_tokens_outline": max_tokens_outline,
        "custom_waypoints": waypoints,
        
        # Quality enhancement parameters
        "sensory_modes": sensory_modes,
        "opener_penalty_threshold": opener_penalty_threshold,
        "transition_penalty_weight": transition_penalty_weight,
        "redundancy_penalty_weight": redundancy_penalty_weight,
        "beat_planning_enabled": beat_planning,
        "beat_length_tolerance": beat_length_tolerance,
        
        # Sleep taper parameters
        "taper_start_percentage": taper_start_percentage,
        "taper_reduction_factor": taper_reduction_factor,
        
        # TTS parameters
        "tts_pause_min": tts_pause_min,
        "tts_pause_max": tts_pause_max,
        "tts_breathe_frequency": tts_breathe_frequency
    }
    
    if models_dict:
        payload["models"] = models_dict
    
    logger.info(f"Starting generation with payload: {json.dumps(payload, indent=2)}")
    
    # Start generation job
    try:
        r = requests.post(f"{API_URL}/generate/story", json=payload, timeout=30)
        if r.status_code != 200:
            error_msg = f"❌ Error starting generation: {r.status_code}\n{r.text}"
            yield (error_msg, "", "", "", "", "")
            return
            
        job = r.json()
        job_id = job.get("job_id")
        
        if not job_id:
            yield ("❌ No job ID returned from backend", "", "", "", "", "")
            return
            
    except requests.exceptions.Timeout:
        yield ("❌ Timeout starting generation (>30s)", "", "", "", "", "")
        return
    except Exception as e:
        yield (f"❌ Error starting generation: {str(e)}", "", "", "", "", "")
        return
    
    # Stream progress using polling (Gradio compatible)
    last_status = ""
    
    while True:
        try:
            # Poll job status
            status_r = requests.get(f"{API_URL}/generate/{job_id}/status", timeout=10)
            if status_r.status_code != 200:
                yield (f"❌ Error polling status: {status_r.status_code}", "", "", "", "", "")
                return
            
            status_data = status_r.json()
            
            elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7]
            
            # Build status display
            features = status_data.get("enhanced_features", {})
            model_info = "Qwen3-8B + DeepSeek-R1-8B + Mistral-7B" if features.get('multi_model') else "Single Model"
            
            progress = status_data.get("progress", 0)
            current_step = status_data.get("current_step", "Processing...")
            step_num = status_data.get("current_step_number", 0)
            total_steps = status_data.get("total_steps", 8)
            
            bar_filled = int(progress / 2.5)
            bar = f"[{'🟩' * bar_filled}{'⬜' * (40 - bar_filled)}] {progress:.1f}%"
            
            status_text = f"""🚀 Enhanced Sleep Stories AI Generator - Complete v2.4

Job: {job_id}
Model Stack: {model_info}
Elapsed: {elapsed}

Features Active:
- 🔥 Multi-Model: {'YES' if features.get('multi_model') else 'NO'}
- 🎯 Quality Enhanced: {'YES' if features.get('quality_enhancements') else 'NO'}
- 🎤 TTS Markers: {'YES' if features.get('tts_markers') else 'NO'}
- 📋 Strict Schema: {'YES' if features.get('strict_schema') else 'NO'}

Status: {status_data.get('status', 'UNKNOWN').upper()}
Step: {step_num}/{total_steps} - {current_step}
{bar}"""
            
            # Only yield if status changed
            if status_text != last_status:
                yield (status_text, "", "", "", "", job_id)
                last_status = status_text
            
            # Check for completion
            if status_data.get("status") == "completed":
                break
            elif status_data.get("status") == "failed":
                error = status_data.get("error", "Unknown error")
                final_status = status_text + f"\n\n❌ GENERATION FAILED: {error}"
                yield (final_status, "", "", "", "", job_id)
                return
            
            # Wait before next poll
            time.sleep(2)
            
        except Exception as e:
            yield (f"❌ Polling error: {str(e)}", "", "", "", "", "")
            return
    
    # Get final results
    try:
        logger.info(f"Fetching final results for job {job_id}")
        res = requests.get(f"{API_URL}/generate/{job_id}/result", timeout=30)
        
        if res.status_code != 200:
            error_msg = f"❌ Error getting results: {res.status_code}\n{res.text[:200]}"
            yield (last_status + "\n\n" + error_msg, "", "", "", "", job_id)
            return
            
        data = res.json()
        
    except Exception as e:
        yield (last_status + f"\n\n❌ Error fetching results: {str(e)}", "", "", "", "", job_id)
        return
    
    # Process results
    story_text = data.get('story_text', '')
    metrics = data.get('metrics', {})
    coherence = data.get('coherence_stats', {})
    memory = data.get('memory_stats', {})
    info = data.get('generation_info', {})
    beats_schema = data.get('beats_schema', {})
    
    total_elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7]
    
    # Build comprehensive metrics text
    metrics_text = (
        "📊 ENHANCED METRICS & PERFORMANCE\n\n"
        f"⏱️  TIMING:\n"
        f"Total Time: {total_elapsed}\n"
        f"Target Duration: {duration} min\n\n"
        f"📝 CONTENT METRICS:\n"
        f"Final Words: {metrics.get('english_word_count', len(story_text.split())):,}\n"
        f"Target Words: {metrics.get('target_words', duration * 150):,}\n"
        f"Accuracy: {metrics.get('accuracy_percent', 0):.1f}% deviation\n"
        f"Beats Generated: {info.get('beats_generated', 0)}\n\n"
        f"🤖 MODEL PERFORMANCE:\n"
        f"Generator (Qwen3-8B): {metrics.get('generator_words', 0):,} words\n"
        f"Reasoner (DeepSeek-R1): {metrics.get('reasoner_words', 0):,} words\n"
        f"Polisher (Mistral-7B): {metrics.get('polisher_words', 0):,} words\n\n"
        f"📈 QUALITY METRICS:\n"
        f"Corrections Applied: {metrics.get('corrections_count', 0)}\n"
        f"Coherence Improvements: {metrics.get('coherence_improvements', 0)}\n"
        f"Sensory Transitions: {coherence.get('sensory_transitions', 0)}\n"
        f"Average Density Factor: {coherence.get('avg_density_factor', 1.0):.2f}\n\n"
        f"🧠 MEMORY STATS:\n"
        f"Total Beats: {memory.get('total_beats', 0)}\n"
        f"Avg Words/Beat: {memory.get('avg_words_per_beat', 0):.0f}\n"
        f"Sensory Distribution: {json.dumps(memory.get('sensory_distribution', {}), indent=2)}"
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
    final_status = last_status + f"\n\n✅ COMPLETED in {total_elapsed}! Ready for Week 2 (Audio/Video)"
    
    yield (final_status, story_text, metrics_text, outline_text, schema_text, job_id)

def attach_to_job_and_stream(job_id: str) -> Generator[tuple, None, None]:
    """Attach to existing job and stream its progress."""
    
    if not job_id:
        yield ("❌ Please select a job to attach to", "", "", "", "", "")
        return
    
    start_time = time.time()
    
    # Test if job exists
    try:
        status_r = requests.get(f"{API_URL}/generate/{job_id}/status", timeout=10)
        if status_r.status_code == 404:
            yield ("❌ Job not found or expired", "", "", "", "", "")
            return
        elif status_r.status_code != 200:
            yield (f"❌ Error accessing job: {status_r.status_code}", "", "", "", "", "")
            return
    except Exception as e:
        yield (f"❌ Error connecting to job: {str(e)}", "", "", "", "", "")
        return
    
    # Stream progress (same logic as new job)
    last_status = ""
    
    while True:
        try:
            status_r = requests.get(f"{API_URL}/generate/{job_id}/status", timeout=10)
            if status_r.status_code != 200:
                yield (f"❌ Error polling status: {status_r.status_code}", "", "", "", "", "")
                return
            
            status_data = status_r.json()
            elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7]
            
            features = status_data.get("enhanced_features", {})
            progress = status_data.get("progress", 0)
            current_step = status_data.get("current_step", "Processing...")
            step_num = status_data.get("current_step_number", 0)
            total_steps = status_data.get("total_steps", 8)
            
            bar_filled = int(progress / 2.5)
            bar = f"[{'🟩' * bar_filled}{'⬜' * (40 - bar_filled)}] {progress:.1f}%"
            
            status_text = f"""🔗 ATTACHED TO EXISTING JOB

Job: {job_id}
Attached for: {elapsed}

Status: {status_data.get('status', 'UNKNOWN').upper()}
Step: {step_num}/{total_steps} - {current_step}
{bar}"""
            
            if status_text != last_status:
                yield (status_text, "", "", "", "", job_id)
                last_status = status_text
            
            if status_data.get("status") == "completed":
                break
            elif status_data.get("status") == "failed":
                error = status_data.get("error", "Unknown error")
                final_status = status_text + f"\n\n❌ JOB FAILED: {error}"
                yield (final_status, "", "", "", "", job_id)
                return
            
            time.sleep(2)
            
        except Exception as e:
            yield (f"❌ Polling error: {str(e)}", "", "", "", "", "")
            return
    
    # Get results (same as new job)
    try:
        res = requests.get(f"{API_URL}/generate/{job_id}/result", timeout=30)
        if res.status_code != 200:
            yield (last_status + f"\n\n❌ Error getting results: {res.status_code}", "", "", "", "", job_id)
            return
        
        data = res.json()
        story_text = data.get('story_text', '')
        # ... same result processing as above ...
        
        final_status = last_status + "\n\n✅ ATTACHED JOB COMPLETED!"
        yield (final_status, story_text, "Results loaded from completed job", "", "", job_id)
        
    except Exception as e:
        yield (last_status + f"\n\n❌ Error fetching results: {str(e)}", "", "", "", "", job_id)
        return

# --- Gradio UI with Complete Controls ---

with gr.Blocks(title="Sleep Stories AI - Complete v2.4", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🌙 Sleep Stories AI - Complete v2.4 (FULL GRADIO STREAMING)")
    
    # Connection status and job management
    with gr.Row():
        with gr.Column(scale=2):
            connection_status = gr.Textbox(label="Backend Status", interactive=False, max_lines=2)
        with gr.Column(scale=2):
            active_jobs = gr.Dropdown(label="Active Jobs (Resume)", choices=[], allow_custom_value=True)
        with gr.Column(scale=1):
            refresh_jobs = gr.Button("↻ Refresh", size="sm")
            attach_btn = gr.Button("🔗 Attach", variant="secondary")
    
    with gr.Row():
        with gr.Column(scale=1):
            # Basic parameters
            gr.Markdown("### 🎨 Basic Settings")
            theme = gr.Textbox(label="Theme / Setting", value="A tranquil mountain meadow with gentle morning mist")
            description = gr.Textbox(label="Additional Details (optional)", lines=3)
            duration = gr.Slider(20, 120, value=45, step=5, label="Duration (minutes)")
            
            # Model selection
            gr.Markdown("### 🤖 Model Configuration")
            use_custom_models = gr.Checkbox(label="Use Custom Models", value=False)
            
            with gr.Row():
                generator_dd = gr.Dropdown(choices=[], label="Generator (Qwen3-8B)", allow_custom_value=True)
                refresh_gen = gr.Button("↻", size="sm")
            with gr.Row():
                reasoner_dd = gr.Dropdown(choices=[], label="Reasoner (DeepSeek-R1-8B)", allow_custom_value=True)
                refresh_r = gr.Button("↻", size="sm")
            with gr.Row():
                polisher_dd = gr.Dropdown(choices=[], label="Polisher (Mistral-7B)", allow_custom_value=True)
                refresh_p = gr.Button("↻", size="sm")
            
            use_reasoner = gr.Checkbox(label="Enable Reasoner Stage", value=True)
            use_polisher = gr.Checkbox(label="Enable Polisher Stage", value=True)
            
            # Quality settings
            gr.Markdown("### 🎯 Quality Enhancement")
            tts_markers = gr.Checkbox(label="Insert TTS Markers [PAUSE:x.x] [BREATHE]", value=False)
            strict_schema = gr.Checkbox(label="Generate Strict JSON Schema", value=False)
            sensory_rotation = gr.Checkbox(label="Enable Sensory Rotation", value=True)
            sleep_taper = gr.Checkbox(label="Enable Sleep Taper (Final Beats)", value=True)
            
            # Advanced parameters
            with gr.Accordion("🔧 Advanced Parameters", open=False):
                gr.Markdown("**Core Generation Settings**")
                model_temperature = gr.Slider(0.1, 2.0, value=0.7, step=0.1, label="Model Temperature")
                target_wpm = gr.Slider(100, 200, value=140, step=10, label="Target WPM (Words Per Minute)")
                words_per_beat = gr.Slider(300, 1000, value=600, step=50, label="Words Per Beat")
                beats_per_story = gr.Slider(8, 20, value=12, step=1, label="Total Beats Per Story")
                max_tokens_beat = gr.Slider(500, 1200, value=800, step=50, label="Max Tokens Per Beat")
                max_tokens_outline = gr.Slider(800, 2000, value=1500, step=100, label="Max Tokens for Outline")
                
                gr.Markdown("**Custom Waypoints & Sensory Modes**")
                custom_waypoints = gr.Textbox(label="Custom Waypoints (comma separated)", 
                                            placeholder="establishing scene, deepening immersion, gentle transition, settling calm")
                sensory_modes = gr.Textbox(label="Sensory Modes (comma separated)", 
                                         value="sight, sound, touch, smell, proprioception",
                                         placeholder="sight, sound, touch, smell, proprioception")
                
                gr.Markdown("**Quality Enhancement Tuning**")
                opener_penalty_threshold = gr.Slider(1, 10, value=3, step=1, label="Opener Penalty Threshold")
                transition_penalty_weight = gr.Slider(0.0, 1.0, value=0.3, step=0.1, label="Transition Penalty Weight")
                redundancy_penalty_weight = gr.Slider(0.0, 1.0, value=0.2, step=0.1, label="Redundancy Penalty Weight")
                beat_planning = gr.Checkbox(label="Enable Beat Planning", value=True)
                beat_length_tolerance = gr.Slider(0.05, 0.3, value=0.1, step=0.05, label="Beat Length Tolerance (±%)")
                
                gr.Markdown("**Sleep Taper Configuration**")
                taper_start_percentage = gr.Slider(0.5, 0.95, value=0.8, step=0.05, label="Taper Start (% of story)")
                taper_reduction_factor = gr.Slider(0.3, 0.9, value=0.7, step=0.1, label="Taper Reduction Factor")
                
                gr.Markdown("**TTS Settings**")
                tts_pause_min = gr.Slider(0.1, 2.0, value=0.5, step=0.1, label="TTS Pause Min (seconds)")
                tts_pause_max = gr.Slider(1.0, 5.0, value=3.0, step=0.1, label="TTS Pause Max (seconds)")
                tts_breathe_frequency = gr.Slider(2, 10, value=4, step=1, label="Breathe Frequency (every N beats)")
            
            # Action buttons
            gr.Markdown("### 🚀 Actions")
            generate_btn = gr.Button("Generate Enhanced Story", variant="primary")
            clear_btn = gr.Button("Clear All")
        
        with gr.Column(scale=2):
            # Current job ID display
            current_job_id = gr.Textbox(label="Current Job ID", interactive=False, visible=True)
            
            # Status display
            status = gr.Textbox(label="Status (Real-time Gradio Streaming)", lines=16, interactive=False)
            
            # Results tabs
            with gr.Tabs():
                with gr.Tab("Story"):
                    story_output = gr.Textbox(lines=26, interactive=False, show_copy_button=True)
                with gr.Tab("Enhanced Metrics"):
                    metrics_output = gr.Textbox(lines=26, interactive=False, show_copy_button=True)
                with gr.Tab("Outline"):
                    outline_output = gr.Textbox(lines=26, interactive=False, show_copy_button=True)
                with gr.Tab("JSON Schema"):
                    schema_output = gr.Textbox(lines=26, interactive=False, show_copy_button=True)
    
    # Initialize UI on load
    def init_complete_ui():
        models = fetch_ollama_models()
        jobs = fetch_active_jobs()
        connected, conn_msg, health_data = test_backend_connection()
        status_msg = f"✅ {conn_msg}" if connected else f"❌ {conn_msg}"
        
        # Load presets if available
        presets = get_model_presets()
        defaults = presets.get("default_models", {})
        
        return (
            gr.update(choices=models, value=defaults.get("generator", "")),
            gr.update(choices=models, value=defaults.get("reasoner", "")), 
            gr.update(choices=models, value=defaults.get("polisher", "")),
            gr.update(choices=jobs),
            status_msg
        )
    
    demo.load(
        fn=init_complete_ui, 
        inputs=None, 
        outputs=[generator_dd, reasoner_dd, polisher_dd, active_jobs, connection_status]
    )
    
    # Refresh functions
    def refresh_models_and_jobs():
        models = fetch_ollama_models()
        jobs = fetch_active_jobs()
        return gr.update(choices=jobs), gr.update(choices=models), gr.update(choices=models), gr.update(choices=models)
    
    refresh_jobs.click(
        fn=refresh_models_and_jobs,
        inputs=None,
        outputs=[active_jobs, generator_dd, reasoner_dd, polisher_dd]
    )
    
    refresh_gen.click(fn=lambda: gr.update(choices=fetch_ollama_models()), inputs=None, outputs=[generator_dd])
    refresh_r.click(fn=lambda: gr.update(choices=fetch_ollama_models()), inputs=None, outputs=[reasoner_dd])
    refresh_p.click(fn=lambda: gr.update(choices=fetch_ollama_models()), inputs=None, outputs=[polisher_dd])
    
    # Main generation with all parameters
    generate_btn.click(
        fn=start_job_and_stream,
        inputs=[
            # Basic
            theme, duration, description,
            # Models
            use_custom_models, generator_dd, reasoner_dd, polisher_dd, use_reasoner, use_polisher,
            # Quality
            tts_markers, strict_schema, sensory_rotation, sleep_taper,
            # Advanced
            model_temperature, target_wpm, words_per_beat, beats_per_story, max_tokens_beat, max_tokens_outline, custom_waypoints,
            # Sensory
            sensory_modes, opener_penalty_threshold, transition_penalty_weight, redundancy_penalty_weight, beat_planning, beat_length_tolerance,
            # Sleep taper
            taper_start_percentage, taper_reduction_factor,
            # TTS
            tts_pause_min, tts_pause_max, tts_breathe_frequency
        ],
        outputs=[status, story_output, metrics_output, outline_output, schema_output, current_job_id]
    )
    
    # Attach to existing job
    attach_btn.click(
        fn=attach_to_job_and_stream,
        inputs=[active_jobs],
        outputs=[status, story_output, metrics_output, outline_output, schema_output, current_job_id]
    )
    
    # Clear function
    clear_btn.click(
        fn=lambda: ("", "", "", "", "", ""), 
        inputs=None,
        outputs=[status, story_output, metrics_output, outline_output, schema_output, current_job_id]
    )

# Enable Gradio queue for streaming support
demo.queue(concurrency_count=3)

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0", 
        server_port=7860, 
        share=False, 
        show_error=True,
        debug=True
    )

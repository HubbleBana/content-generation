"""Helper utilities for Sleep Stories AI Frontend."""

import gradio as gr
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
import json

def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

def format_timestamp(iso_string: str) -> str:
    """Format ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime("%H:%M:%S")
    except Exception:
        return iso_string

def create_progress_bar(progress: float, width: int = 40) -> str:
    """Create ASCII progress bar."""
    filled = int(progress * width / 100)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}] {progress:.1f}%"

def format_job_status(telemetry: Dict[str, Any]) -> str:
    """Format comprehensive job status display."""
    status = telemetry.get("status", "unknown")
    progress = telemetry.get("progress", 0)
    current_step = telemetry.get("current_step", "Processing...")
    step_num = telemetry.get("current_step_number", 0)
    total_steps = telemetry.get("total_steps", 8)
    
    # Beat information
    beat_info = telemetry.get("beat", {})
    beat_index = beat_info.get("index", 0)
    beat_total = beat_info.get("total", 0)
    beat_stage = beat_info.get("stage", "")
    beat_progress = beat_info.get("stage_progress", 0)
    
    # Timing information
    timing = telemetry.get("timing", {})
    elapsed = timing.get("elapsed_sec", 0)
    eta = timing.get("eta_sec")
    
    # Model information
    models = telemetry.get("models", {})
    
    # Create status display
    lines = [
        "🌙 Sleep Stories AI - Generation Status",
        "" + "="*50,
        f"Status: {status.upper()}",
        f"Progress: {create_progress_bar(progress)}",
        f"Step: {step_num}/{total_steps} - {current_step}",
        ""
    ]
    
    # Add beat information if available
    if beat_total > 0:
        lines.extend([
            f"📝 Beat Progress: {beat_index}/{beat_total}",
            f"Current Stage: {beat_stage} ({beat_progress}%)",
            ""
        ])
    
    # Add timing information
    lines.append(f"⏱️ Elapsed: {format_duration(elapsed)}")
    if eta is not None:
        lines.append(f"⏳ ETA: {format_duration(eta)}")
    lines.append("")
    
    # Add model information
    if models:
        lines.extend([
            "🤖 Models:",
            f"  Generator: {models.get('generator', 'N/A')}",
            f"  Reasoner: {models.get('reasoner', 'N/A')}",
            f"  Polisher: {models.get('polisher', 'N/A')}",
            ""
        ])
    
    return "\n".join(lines)

def format_generation_result(result: Dict[str, Any]) -> Tuple[str, str, str, str]:
    """Format generation result into display components."""
    # Story text
    story_text = result.get("story_text", "")
    
    # Metrics and coherence
    metrics = result.get("metrics", {})
    coherence = result.get("coherence_stats", {})
    memory_stats = result.get("memory_stats", {})
    
    metrics_text = "📊 Generation Metrics\n" + "="*30 + "\n"
    metrics_text += json.dumps(metrics, indent=2)
    
    if coherence:
        metrics_text += "\n\n🧠 Coherence Stats\n" + "="*30 + "\n"
        metrics_text += json.dumps(coherence, indent=2)
    
    if memory_stats:
        metrics_text += "\n\n💾 Memory Stats\n" + "="*30 + "\n"
        metrics_text += json.dumps(memory_stats, indent=2)
    
    # Outline (if available)
    outline = result.get("outline", "No outline available")
    
    # Schema (if available)
    schema = result.get("beats_schema", {})
    schema_text = json.dumps(schema, indent=2) if schema else "No schema available"
    
    return story_text, metrics_text, outline, schema_text

def validate_generation_params(params: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate generation parameters."""
    errors = []
    
    # Required fields
    if not params.get("theme", "").strip():
        errors.append("Theme is required")
    
    # Duration validation
    duration = params.get("duration", 0)
    if not (5 <= duration <= 180):
        errors.append("Duration must be between 5 and 180 minutes")
    
    # Model validation (if custom models specified)
    models = params.get("models", {})
    if models:
        for model_type in ["generator", "reasoner", "polisher"]:
            model_name = models.get(model_type)
            if model_name and not model_name.strip():
                errors.append(f"{model_type.title()} model name cannot be empty if specified")
    
    # Temperature validation
    advanced = params.get("advanced", {})
    temp = advanced.get("model_temperature", 0.7)
    if not (0.1 <= temp <= 2.0):
        errors.append("Model temperature must be between 0.1 and 2.0")
    
    if errors:
        return False, "; ".join(errors)
    
    return True, "Parameters are valid"

def create_model_choices_update(models: List[Dict[str, Any]]) -> gr.update:
    """Create Gradio update for model dropdown choices."""
    choices = [model.get("name", "") for model in models if isinstance(model, dict)]
    return gr.update(choices=choices, value=None)

def create_job_choices_update(jobs: List[Dict[str, Any]], api_client) -> gr.update:
    """Create Gradio update for job dropdown choices."""
    choices = [api_client.format_job_label(job) for job in jobs]
    return gr.update(choices=choices, value=None)

def create_status_update(status_text: str) -> gr.update:
    """Create Gradio update for status display."""
    return gr.update(value=status_text)

def create_result_updates(
    story: str, 
    metrics: str, 
    outline: str, 
    schema: str
) -> Tuple[gr.update, gr.update, gr.update, gr.update]:
    """Create Gradio updates for all result displays."""
    return (
        gr.update(value=story),
        gr.update(value=metrics),
        gr.update(value=outline),
        gr.update(value=schema)
    )

def get_preset_values(preset_name: str, presets: Dict[str, Any]) -> Dict[str, Any]:
    """Get parameter values for a specific preset."""
    preset_data = presets.get(preset_name, {})
    
    # Default values
    defaults = {
        "use_reasoner": True,
        "use_polisher": True,
        "tts_markers": False,
        "strict_schema": False,
        "sensory_rotation": True,
        "sleep_taper": True,
        "model_temperature": 0.7,
        "models": {}
    }
    
    # Merge with preset data
    result = {**defaults, **preset_data}
    
    return result

def format_error_message(error: str) -> str:
    """Format error message for display."""
    return f"❌ Error: {error}"

def format_success_message(message: str) -> str:
    """Format success message for display."""
    return f"✅ Success: {message}"

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to specified length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."
